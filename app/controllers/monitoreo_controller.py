import json
import os
import threading
import time

from PySide6.QtCore import QTimer, QThread, QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication

from app.config import EVIDENCIAS_DIR
from app.models import incidencia_model, evidencia_model, fatiga_model, comando_model, dispositivo_dvr_model
from app.services.camera_service import CamaraThread, SEGUNDOS_FOTO_ANTES
from app.services.grabador_info import IdentificarGrabadoresThread
from app.services.hash_service import firmar_archivo
from app.services.fatiga_service import AuditorFatiga
from app.services.voice_service import GrabacionVozThread, interpretar_comando, hablar
from app.services.panic_service import DetectorPanicoThread
from app.services.ptz_service import MovimientoPTZThread, PresetPTZThread, _datos_conexion
from app.services import alertas_service, alarma_service, imou_cloud
from app.services.linea_virtual import DetectorLinea
from app.services.ia_personas import AnalizadorIA, calcular_homografia, dibujar as dibujar_personas
from app.services import avistamientos
from app.views.UI.zona_ampliada_dialog import ZonaAmpliadaDialog

import cv2


class _ConsultaDispositivosThread(QThread):
    """Trae los datos de cada DVR/NVR desde la base en un hilo aparte: antes
    se consultaba en el hilo de la UI al abrir sesion (un viaje a la base
    por cada grabador), lo que trababa la ventana un instante justo al
    entrar. Solo lee - la consulta de red a cada equipo sigue siendo
    responsabilidad de IdentificarGrabadoresThread."""
    listos = Signal(list)

    def __init__(self, ids, parent=None):
        super().__init__(parent)
        self._ids = ids

    def run(self):
        self.listos.emit(dispositivo_dvr_model.obtener_varios(self._ids))


class _GuardarEvidenciaSabotajeThread(QThread):
    """El INSERT de la incidencia, el hash SHA-256 de foto+video y los
    INSERT de evidencia corrian en el slot de la senal sabotaje_detectado,
    es decir en el hilo de la UI: mientras duraban, las demas camaras se
    quedaban sin pintar su siguiente cuadro. Esto hace ese trabajo aca y
    devuelve lo que la UI necesita (mensaje de registro, foto+hash para la
    alerta al celular) por senal."""
    listo = Signal(str, str, object, bool)  # zona, mensaje_evento, (ruta_foto, hash_foto) o None, es_simulacro

    def __init__(self, zona, camara_info, ruta_video, ruta_foto, id_usuario, id_turno,
                 tipo="Sabotaje", severidad="Alta", parent=None):
        super().__init__(parent)
        self._zona = zona
        self._camara_info = camara_info
        self._ruta_video = ruta_video
        self._ruta_foto = ruta_foto
        self._id_usuario = id_usuario
        self._id_turno = id_turno
        self._tipo = tipo
        self._severidad = severidad

    def run(self):
        camara_info = self._camara_info
        id_incidencia = incidencia_model.crear(
            camara_info["IdZona"], self._tipo,
            "Camara tapada/movida - deteccion automatica (buffer de 8s exportado)",
            id_camara=camara_info["IdCamara"], id_turno=self._id_turno, severidad=self._severidad,
        )
        hash_foto = None
        for ruta, tipo in [(self._ruta_foto, "Foto"), (self._ruta_video, "Video")]:
            if os.path.exists(ruta):
                hash_archivo = firmar_archivo(ruta)
                if tipo == "Foto":
                    hash_foto = hash_archivo
                evidencia_model.crear(
                    camara_info["IdZona"], ruta, tipo, hash_archivo,
                    id_usuario=self._id_usuario, id_incidencia=id_incidencia,
                )
        es_simulacro = self._tipo == "Simulacro"
        if es_simulacro:
            mensaje = (
                f"[SIMULACRO] Simulacro en {self._zona}: foto y video (8s previos) firmados con SHA-256 y guardados."
            )
        else:
            mensaje = (
                f"[EVIDENCIA] Sabotaje en {self._zona}: foto y video (8s previos) firmados con SHA-256 y guardados."
            )
        datos_alerta = (self._ruta_foto, hash_foto) if (os.path.exists(self._ruta_foto) and hash_foto) else None
        self.listo.emit(self._zona, mensaje, datos_alerta, es_simulacro)


class _PuenteAlertas(QObject):
    """alertas_service envia desde un hilo Python comun (no QThread); una
    senal Qt es la forma segura de volver al hilo de la UI para actualizar
    la bitacora sin tocar widgets desde otro hilo."""
    resultado = Signal(bool, str)


class _PuenteSimulacro(QObject):
    """El simulacro llega desde el telefono por la API (hilo de uvicorn, no
    el de la UI); la alarma toca un QTimer, un QSoundEffect y botones, asi
    que se salta al hilo de la UI con una senal (en el mismo hilo sigue
    siendo una llamada directa)."""
    disparado = Signal()


class MonitoreoController:
    def __init__(self, dashboard_view, usuario, camaras, obtener_turno_actual):
        self.view = dashboard_view
        self.usuario = usuario
        self.obtener_turno_actual = obtener_turno_actual

        # un recuadro/hilo por CAMARA, con su "Clave" (su nombre) como llave;
        # los nombres heredados "zona"/"por_zona" de aqui abajo se refieren a esa clave
        self.camaras_por_zona = {c["Clave"]: c for c in camaras}
        self.hilos_camara = {}
        self.dialogos_ampliados = {}
        self._estados = {}  # clave -> ultimo estado (para el resumen de Inicio)
        self.factor_zoom = {}
        # quienes quieren saber cuanto movimiento ve cada camara (ej. el Mapa
        # del lugar): funciones (clave, nivel 0..1), ~2 veces por segundo
        self.oyentes_movimiento = []
        # idem con lo que ve la IA de personas: funciones (clave, [personas])
        self.oyentes_personas = []
        # lista, no una sola variable: si se mueven dos camaras (zonas
        # distintas) casi al mismo tiempo, una sola variable pierde la
        # referencia a la primera mientras todavia esta corriendo (riesgo
        # de que Python la recolecte a mitad de la llamada ONVIF)
        self._hilos_ptz_activos = []

        self._puente_alertas = _PuenteAlertas()
        self._puente_alertas.resultado.connect(
            lambda ok, msg: self.view.registrar_evento(f"[ALERTA AL CELULAR] {msg}")
        )
        self._puente_simulacro = _PuenteSimulacro()
        self._puente_simulacro.disparado.connect(self._activar_alarma)

        self.view.capturar_evidencia.connect(self.capturar_evidencia)
        self.view.ampliar_zona.connect(self.ampliar_zona)
        self.view.reconectar_zona.connect(self.reconectar_camara)
        self.view.comando_manual_enviado.connect(self._procesar_comando_manual)
        self.view.hablar_presionado.connect(self._empezar_a_hablar)
        self.view.hablar_soltado.connect(self._terminar_de_hablar)
        self.view.deteccion_gesto_alternada.connect(self._alternar_deteccion_gesto)
        self.view.panico_manual.connect(self.activar_panico)
        self.view.fatiga_confirmada.connect(self._confirmar_fatiga)
        self.view.alarma_silenciada.connect(lambda: self._silenciar_alarma("silenciada por el vigilante"))
        self.view.ocultar_zona.connect(self.ocultar_camara)
        self.view.mostrar_zona.connect(self.mostrar_camara)

        # camaras suspendidas ("Ocultar"): no se conectan ni se ven. Se guarda
        # por IdCamara en la configuracion de ESTA PC (QSettings), no en la
        # base: cada puesto de monitoreo decide que quiere ver sin cambiarle
        # nada a los demas, y no hace falta tocar el esquema de la BD
        self._ajustes = QSettings("ProyectoCAM", "CentroMonitoreo")
        self._ids_ocultos = self._leer_ids_ocultos()
        self._zonas_ocultas = {c["Clave"] for c in camaras if c["IdCamara"] in self._ids_ocultos}
        for zona in self._zonas_ocultas:
            self.view.set_zona_oculta(zona, True)

        # sirena de camara tapada: suena mientras haya alguna zona en
        # sabotaje; se apaga sola al destaparlas, con el boton, o al llegar
        # al tiempo maximo (para no sonar toda la noche si nadie esta)
        self._zonas_en_sabotaje = set()
        self._alarma_sonando = False
        alarma_service.preparar()
        self._timer_alarma = QTimer()
        self._timer_alarma.setSingleShot(True)
        self._timer_alarma.timeout.connect(lambda: self._silenciar_alarma("paso el tiempo maximo de 60 s"))

        self.hilo_voz = None
        self._hilos_voz_terminando = []
        self.detector_panico = None
        self._gesto_activando = False

        # cola de arranque: iniciar dos o mas hilos que cargan librerias
        # nativas pesadas (FFmpeg de cada camara) al mismo tiempo resulto
        # inestable (crash) - tanto al iniciar sesion como al agregar una
        # camara nueva mientras otra recien estaba arrancando. Por eso TODO
        # arranque nativo (el inicial y cualquiera agregado despues en
        # caliente) pasa por _programar_arranque_nativo, que los serializa.
        # El detector de gestos (mediapipe/TensorFlow Lite, el mas pesado de
        # todos) ya NO arranca solo: queda apagado hasta que el usuario
        # active la casilla "Activar deteccion de gesto", asi nunca compite
        # con el arranque de las camaras ni gasta CPU/RAM de mas por defecto.
        self._proximo_arranque_disponible = 0.0
        for camara in camaras:
            if camara["Clave"] in self._zonas_ocultas:
                continue  # suspendida: ni se conecta (no ocupa conexion del DVR ni CPU)
            self._programar_arranque_nativo(lambda c=camara: self._iniciar_hilo_camara(c))
        self._identificar_grabadores()

        self.fatiga = AuditorFatiga()
        self.fatiga.pedir_confirmacion.connect(self._pedir_confirmacion_fatiga)
        self.fatiga.fatiga_detectada.connect(self._fatiga_detectada)
        self.fatiga.confirmado.connect(self._fatiga_confirmada_ok)
        self.fatiga.iniciar()

        self._actualizar_manual_ptz()

    def _actualizar_manual_ptz(self):
        """El manual de comandos (boton "Ver manual de comandos") solo debe
        ofrecer mover/presets en las zonas que de verdad tienen una camara
        con motor PTZ marcado ahora mismo - se recalcula cada vez que una
        camara se agrega o se quita."""
        zonas_con_ptz = sorted(z for z, c in self.camaras_por_zona.items() if c.get("TienePTZ"))
        self.view.actualizar_disponibilidad_ptz(zonas_con_ptz)

    # margenes entre arranques de hilos nativos (ver _programar_arranque_nativo):
    # se eligieron observando cuanto tarda cada uno en terminar de verdad, no
    # solo en "empezar" - un margen mas corto dejaba crashes intermitentes
    PASO_ARRANQUE_SEG = 0.8
    PASO_ARRANQUE_PANICO_SEG = 2.5

    def encolar_arranque_nativo(self, funcion, paso_seg=None):
        """Punto de entrada publico para OTROS controladores (ej.
        CamaraController, al probar una conexion o detectar camaras USB
        desde la pestana "Camaras"): usan la misma cola de abajo para que
        esos intentos nunca abran FFmpeg/OpenCV al mismo tiempo que una
        camara del Centro de Monitoreo esta arrancando o reconectando."""
        self._programar_arranque_nativo(funcion, paso_seg=paso_seg)

    def _programar_arranque_nativo(self, funcion, paso_seg=None):
        """Serializa el arranque de hilos que inicializan librerias nativas
        pesadas (FFmpeg por camara, mediapipe): nunca se inician dos a la
        vez, sin importar si es el arranque inicial o una camara agregada
        en caliente poco despues de otra."""
        paso_seg = self.PASO_ARRANQUE_SEG if paso_seg is None else paso_seg
        ahora = time.time()
        espera = max(0.0, self._proximo_arranque_disponible - ahora)
        self._proximo_arranque_disponible = ahora + espera + paso_seg
        QTimer.singleShot(int(espera * 1000), funcion)

    def _alternar_deteccion_gesto(self, activar):
        if activar:
            if self.detector_panico is not None or self._gesto_activando:
                return  # ya esta activa, o ya se programo su arranque
            # el arranque real queda programado con un retraso (paso_seg),
            # asi que self.detector_panico sigue en None hasta que de verdad
            # arranca: esta bandera es la que de verdad marca "ya pedido",
            # para no programar dos arranques si se alterna rapido el
            # checkbox (eso terminaba creando dos detectores de mediapipe a
            # la vez sobre la misma camara, uno de ellos huerfano)
            self._gesto_activando = True
            self.view.lbl_estado_gesto.setText("Deteccion de gesto: activando...")
            self._programar_arranque_nativo(self._iniciar_detector_panico, paso_seg=self.PASO_ARRANQUE_PANICO_SEG)
        else:
            self._gesto_activando = False  # cancela el arranque si aun no se habia disparado
            if self.detector_panico is None:
                return
            hilo_webcam = self.hilos_camara.get(self._clave_panico())
            if hilo_webcam:
                try:
                    hilo_webcam.frame_listo.disconnect(self.detector_panico.alimentar_frame)
                except TypeError:
                    pass
            self.detector_panico.detener()
            self.detector_panico.finished.connect(self.detector_panico.deleteLater)
            self.detector_panico = None
            self.view.lbl_estado_gesto.setText("Deteccion de gesto: desactivada")

    def _iniciar_detector_panico(self):
        if not self._gesto_activando:
            return  # el usuario lo desactivo antes de que le tocara arrancar
        self._gesto_activando = False
        self.detector_panico = DetectorPanicoThread()
        self.detector_panico.gesto_detectado.connect(self.activar_panico)
        self.detector_panico.no_disponible.connect(
            lambda msg: self.view.lbl_estado_gesto.setText(f"Deteccion de gesto: {msg}")
        )
        self.detector_panico.started.connect(
            lambda: self.view.lbl_estado_gesto.setText("Deteccion de gesto: activa en la webcam")
        )
        self.detector_panico.progreso.connect(self._actualizar_progreso_gesto)
        hilo_webcam = self.hilos_camara.get(self._clave_panico())
        if hilo_webcam:
            hilo_webcam.frame_listo.connect(self.detector_panico.alimentar_frame)
        self.detector_panico.start()

    def resumen_camaras(self):
        """(en linea, total) de las camaras no ocultas."""
        visibles = [k for k in self.camaras_por_zona if k not in self._zonas_ocultas]
        en_linea = sum(1 for k in visibles if self._estados.get(k) in ("conectada", "reconectando"))
        return en_linea, len(visibles)

    def estado_camaras(self):
        """Estado en vivo de cada camara no oculta - lo unico que sabe esto
        es esta instancia (no esta en la base): lo usa la API para la app
        de Android, igual que el resumen de Inicio."""
        return [
            {
                "zona": zona,
                "nombre": camara["Nombre"],
                "en_linea": self._estados.get(zona) in ("conectada", "reconectando"),
                "en_sabotaje": zona in self._zonas_en_sabotaje,
            }
            for zona, camara in self.camaras_por_zona.items()
            if zona not in self._zonas_ocultas
        ]

    def _clave_panico(self):
        """El gesto de panico se mira en la webcam de la PC (la que tiene
        delante el vigilante): la primera camara USB registrada."""
        return next((k for k, c in self.camaras_por_zona.items() if c["TipoConexion"] == "USB"), None)

    def _camara_panico(self):
        """Camara a la que se asignan las incidencias de panico/fatiga: la
        webcam, o cualquiera si no hay webcam."""
        return self.camaras_por_zona.get(self._clave_panico()) or next(iter(self.camaras_por_zona.values()), None)

    # ---------------- alta de camaras (cualquier marca) ----------------
    def _iniciar_hilo_camara(self, camara):
        zona = camara["Clave"]
        # el arranque se programa con retraso (cola nativa): para cuando le
        # toca, la camara pudo haberse ocultado, quitado o reemplazado
        actual = self.camaras_por_zona.get(zona)
        if zona in self._zonas_ocultas or not actual or actual["IdCamara"] != camara["IdCamara"]:
            return None
        hilo_anterior = self.hilos_camara.get(zona)
        if hilo_anterior and hilo_anterior.id_camara == camara["IdCamara"] and hilo_anterior.isRunning():
            return hilo_anterior  # ya esta corriendo (ej. Mostrar pulsado dos veces)
        self.factor_zoom.setdefault(zona, 1.0)

        # si ya habia un hilo corriendo para esta zona (ej. dos camaras
        # registradas en la misma zona), se detiene antes de arrancar el
        # nuevo: evita dos hilos nativos (FFmpeg) compitiendo por el mismo
        # recuadro, lo que en la practica resulto inestable
        if hilo_anterior:
            self._retirar_hilo(hilo_anterior)

        hilo = CamaraThread(
            camara["IdCamara"], zona, camara["Nombre"],
            camara["TipoConexion"], camara["UrlConexion"],
        )
        hilo.frame_listo.connect(lambda frame, z=zona: self._on_frame(z, frame))
        hilo.estado_cambiado.connect(lambda estado, z=zona: self._on_estado(z, estado))
        hilo.sabotaje_detectado.connect(self._on_sabotaje)
        hilo.cruce_linea.connect(lambda s, e, sa, z=zona: self._on_cruce_linea(z, s, e, sa))
        hilo.movimiento.connect(lambda nivel, z=zona: self._on_movimiento(z, nivel))
        hilo.personas_detectadas.connect(lambda personas, z=zona: self._on_personas(z, personas))
        linea = self._leer_linea(camara["IdCamara"])
        if linea:
            hilo.detector_linea = DetectorLinea(*linea)
        if self._ajustes.value(f"ia/{camara['IdCamara']}", "") == "1":
            self._encender_ia(hilo, camara["IdCamara"])
        self.hilos_camara[zona] = hilo
        hilo.start()
        if zona == self._clave_panico() and getattr(self, "detector_panico", None):
            hilo.frame_listo.connect(self.detector_panico.alimentar_frame)
        return hilo

    def _retirar_hilo(self, hilo):
        """Detiene un hilo de camara sin destruirlo mientras sigue corriendo:
        puede estar hasta ~4s dentro de una apertura RTSP (timeout real), y
        soltar la ultima referencia a un QThread vivo cierra la app de golpe.
        Se guarda en _hilos_retirados hasta que termine solo."""
        hilo.detener()
        try:
            hilo.frame_listo.disconnect()
            hilo.estado_cambiado.disconnect()
            hilo.sabotaje_detectado.disconnect()
            hilo.cruce_linea.disconnect()
            hilo.movimiento.disconnect()
            hilo.personas_detectadas.disconnect()
        except TypeError:
            pass
        if hilo.wait(1500):
            return
        retirados = self.__dict__.setdefault("_hilos_retirados", [])
        retirados.append(hilo)
        hilo.finished.connect(lambda h=hilo: h in retirados and retirados.remove(h))

    def agregar_camara(self, camara):
        """Agrega una camara en caliente (su propio recuadro, al lado de las
        demas de su grupo), sin reiniciar la app. Cualquier marca: RTSP sirve
        para IP de cualquier fabricante, USB para webcams locales."""
        camara.setdefault("Clave", camara["Nombre"])
        zona = camara["Clave"]

        self.camaras_por_zona[zona] = camara
        # una camara recien agregada siempre se muestra
        self._zonas_ocultas.discard(zona)
        if camara["IdCamara"] in self._ids_ocultos:
            self._ids_ocultos.discard(camara["IdCamara"])
            self._guardar_ids_ocultos()

        self.view.agregar_zona_frame(camara)
        self._programar_arranque_nativo(lambda c=camara: self._iniciar_hilo_camara(c))
        self._actualizar_manual_ptz()
        self.view.registrar_evento(
            f"[CAMARA] Nueva camara: {camara['Nombre']} ({camara['Marca']}, {camara['TipoConexion']})."
        )
        if camara.get("IdDispositivo"):
            self._identificar_grabadores([camara["IdDispositivo"]])

    def quitar_camara(self, id_camara):
        """Detiene la camara y borra su recuadro por completo del Centro de
        Monitoreo (ni el recuadro, ni la vista ampliada si estaba abierta)."""
        zona = next((k for k, c in self.camaras_por_zona.items() if c["IdCamara"] == id_camara), None)
        if zona is None:
            return
        if zona == self._clave_panico() and self.view.chk_gesto.isChecked():
            # era la webcam del panico silencioso: apagar la deteccion de
            # gesto en vez de dejarla "activa" para siempre sin camara que
            # mirar (el checkbox se desincronizaria del estado real)
            self.view.chk_gesto.setChecked(False)
        hilo = self.hilos_camara.pop(zona, None)
        if hilo:
            self._retirar_hilo(hilo)
        camara = self.camaras_por_zona.pop(zona, None)
        self.factor_zoom.pop(zona, None)
        self._zonas_ocultas.discard(zona)
        if camara and camara["IdCamara"] in self._ids_ocultos:
            self._ids_ocultos.discard(camara["IdCamara"])
            self._guardar_ids_ocultos()
        self._quitar_de_alarma(zona)

        dialogo = self.dialogos_ampliados.pop(zona, None)
        if dialogo:
            dialogo.close()
            dialogo.deleteLater()

        self.view.quitar_zona_frame(zona)
        self._actualizar_manual_ptz()
        self.view.registrar_evento(f"[CAMARA] Camara {zona} quitada por el administrador.")

    # ---------------- ocultar / mostrar (suspender) camaras ----------------
    def _leer_ids_ocultos(self):
        valor = self._ajustes.value("camaras_ocultas", [])
        if isinstance(valor, str):  # QSettings devuelve str si la lista tenia un solo elemento
            valor = [valor]
        ids = set()
        for v in valor or []:
            try:
                ids.add(int(v))
            except (TypeError, ValueError):
                pass
        return ids

    def _guardar_ids_ocultos(self):
        self._ajustes.setValue("camaras_ocultas", [str(i) for i in sorted(self._ids_ocultos)])

    def ocultar_camara(self, zona):
        """Suspende la camara: corta su conexion (libera el canal del
        DVR/NVR y la CPU de decodificar) y la saca de la grilla. Si estaba en
        alarma por sabotaje, esa zona deja de contar para la sirena."""
        camara = self.camaras_por_zona.get(zona)
        if not camara or zona in self._zonas_ocultas:
            return
        self._zonas_ocultas.add(zona)
        self._ids_ocultos.add(camara["IdCamara"])
        self._guardar_ids_ocultos()

        hilo = self.hilos_camara.pop(zona, None)
        if hilo:
            self._retirar_hilo(hilo)
        dialogo = self.dialogos_ampliados.get(zona)
        if dialogo:
            dialogo.close()
        self._quitar_de_alarma(zona)
        self.view.set_zona_oculta(zona, True)
        self.view.registrar_evento(
            f"[CAMARA] {zona} oculta: suspendida (no se ve ni detecta sabotaje). "
            "Para verla de nuevo use el boton \"Ocultas\" de su grupo."
        )

    def mostrar_camara(self, zona):
        camara = self.camaras_por_zona.get(zona)
        if not camara or zona not in self._zonas_ocultas:
            return
        self._zonas_ocultas.discard(zona)
        self._ids_ocultos.discard(camara["IdCamara"])
        self._guardar_ids_ocultos()
        self.view.set_zona_oculta(zona, False)
        self._programar_arranque_nativo(lambda c=camara: self._iniciar_hilo_camara(c))
        self.view.registrar_evento(f"[CAMARA] {zona} visible de nuevo, reconectando...")

    def _quitar_de_alarma(self, zona):
        if zona in self._zonas_en_sabotaje:
            self._zonas_en_sabotaje.discard(zona)
            if not self._zonas_en_sabotaje:
                self._silenciar_alarma(f"{zona} ya no esta en monitoreo")
            elif self._alarma_sonando:
                self.view.set_alarma_sonando(True, sorted(self._zonas_en_sabotaje))

    # ---------------- titulo DVR / NVR de cada grupo ----------------
    def _identificar_grabadores(self, ids=None):
        """Pregunta en segundo plano a cada grabador su modelo, para titular
        su grupo como DVR o NVR (ej. 'NVR "angel" — Dahua · DHI-NVR1108HS').
        Si no responde, el grupo queda como 'Grabador'."""
        ids = set(ids) if ids else {c["IdDispositivo"] for c in self.camaras_por_zona.values() if c.get("IdDispositivo")}
        if not ids:
            return
        hilos = self.__dict__.setdefault("_hilos_identificacion", [])
        consulta = _ConsultaDispositivosThread(ids)
        consulta.listos.connect(self._iniciar_identificacion_grabadores)
        consulta.finished.connect(lambda h=consulta: h in hilos and hilos.remove(h))
        hilos.append(consulta)
        consulta.start()

    def _iniciar_identificacion_grabadores(self, dispositivos):
        if not dispositivos:
            return
        hilos = self.__dict__.setdefault("_hilos_identificacion", [])
        hilo = IdentificarGrabadoresThread(dispositivos)
        hilo.identificado.connect(self._grabador_identificado)
        hilo.finished.connect(lambda h=hilo: h in hilos and hilos.remove(h))
        hilos.append(hilo)
        hilo.start()

    def _grabador_identificado(self, id_dispositivo, tipo, modelo):
        camara = next((c for c in self.camaras_por_zona.values() if c.get("IdDispositivo") == id_dispositivo), None)
        if camara:
            self.view.actualizar_titulo_grabador(
                id_dispositivo, self.view.titulo_grabador(camara, tipo, modelo or None)
            )

    def reconectar_camara(self, zona):
        """Fuerza una reconexion manual (resincroniza el video de inmediato)."""
        hilo = self.hilos_camara.get(zona)
        if not hilo:
            self.view.registrar_evento(f"No hay camara activa en {zona} para reconectar.")
            return
        hilo.forzar_reconexion()
        self.view.registrar_evento(f"[CAMARA] Reconexion solicitada para {zona}.")

    # ---------------- camara: frame, zoom y estado ----------------
    def _aplicar_zoom(self, frame, factor):
        if factor <= 1.0:
            return frame
        alto, ancho = frame.shape[:2]
        nuevo_ancho = max(1, int(ancho / factor))
        nuevo_alto = max(1, int(alto / factor))
        x0 = (ancho - nuevo_ancho) // 2
        y0 = (alto - nuevo_alto) // 2
        recorte = frame[y0:y0 + nuevo_alto, x0:x0 + nuevo_ancho]
        return cv2.resize(recorte, (ancho, alto), interpolation=cv2.INTER_LINEAR)

    def _on_frame(self, zona, frame):
        try:
            factor = self.factor_zoom.get(zona, 1.0)
            if factor > 1.0:
                frame = self._aplicar_zoom(frame, factor)
            zf = self.view.zona_widget(zona)
            if zf:
                zf.mostrar_frame(frame)
            dialogo = self.dialogos_ampliados.get(zona)
            if dialogo and dialogo.isVisible():
                dialogo.mostrar_frame(frame)
        finally:
            # pide el siguiente frame recien ahora (ver CamaraThread.confirmar_entrega)
            hilo = self.hilos_camara.get(zona)
            if hilo:
                hilo.confirmar_entrega()

    def _actualizar_progreso_gesto(self, detectando, segundos):
        if detectando and segundos > 0.2:
            self.view.lbl_estado_gesto.setText(
                f"Deteccion de gesto: ¡mano detectada! sosteniendo {segundos:.1f}s / 3.0s"
            )
        elif detectando:
            self.view.lbl_estado_gesto.setText("Deteccion de gesto: mano detectada...")
        else:
            self.view.lbl_estado_gesto.setText("Deteccion de gesto: activa (sin manos arriba)")

    def _on_estado(self, zona, estado):
        if zona in self._zonas_ocultas:
            return  # aviso rezagado de un hilo ya suspendido
        self._estados[zona] = estado
        zf = self.view.zona_widget(zona)
        if zf:
            zf.actualizar_estado(estado)
        if estado == "sabotaje":
            self.view.registrar_evento(f"[ALERTA] Posible sabotaje detectado en {zona}.")
            self._zonas_en_sabotaje.add(zona)
            self._activar_alarma()
        elif zona in self._zonas_en_sabotaje:
            # se destapo (o perdio senal/reconecta): esa zona ya no cuenta
            self._zonas_en_sabotaje.discard(zona)
            if not self._zonas_en_sabotaje:
                self._silenciar_alarma(motivo="la camara volvio a verse normal")
            elif self._alarma_sonando:
                self.view.set_alarma_sonando(True, sorted(self._zonas_en_sabotaje))

    # ---------------- sirena de camara tapada ----------------
    DURACION_MAXIMA_ALARMA_MS = 60_000

    def _activar_alarma(self):
        if not self._alarma_sonando:
            if not alarma_service.iniciar_sirena():
                QApplication.beep()
            self._alarma_sonando = True
        self._timer_alarma.start(self.DURACION_MAXIMA_ALARMA_MS)
        self.view.set_alarma_sonando(True, sorted(self._zonas_en_sabotaje))

    def _silenciar_alarma(self, motivo):
        if not self._alarma_sonando:
            return
        alarma_service.detener_sirena()
        self._alarma_sonando = False
        self._timer_alarma.stop()
        self.view.set_alarma_sonando(False)
        self.view.registrar_evento(f"[ALARMA] Sirena apagada ({motivo}).")

    # ---------------- sabotaje automatico ----------------
    def _on_sabotaje(self, zona, ruta_video, ruta_foto, es_simulacro=False):
        camara_info = self.camaras_por_zona.get(zona)
        if not camara_info:
            return
        # el hash SHA-256 y los INSERT a la base van en un hilo aparte: hacerlo
        # aca mismo (hilo de la UI) trababa el video de TODAS las camaras
        # mientras duraba (ver _GuardarEvidenciaSabotajeThread)
        hilos = self.__dict__.setdefault("_hilos_evidencia", [])
        hilo = _GuardarEvidenciaSabotajeThread(
            zona, camara_info, ruta_video, ruta_foto,
            self.usuario["IdUsuario"], self.obtener_turno_actual(),
            tipo="Simulacro" if es_simulacro else "Sabotaje",
            severidad="Normal" if es_simulacro else "Alta",
        )
        hilo.listo.connect(self._evidencia_sabotaje_lista)
        hilo.finished.connect(lambda h=hilo: h in hilos and hilos.remove(h))
        hilos.append(hilo)
        hilo.start()
        # (el sonido ya lo da la sirena, que arranca en _on_estado apenas se
        # detecta, sin esperar a que se exporte la evidencia)

    def disparar_simulacro(self, zona):
        """Dispara un simulacro de sabotaje en una zona ya conectada (para la
        demo): reutiliza el mismo pipeline de evidencia que el sabotaje real,
        marcado como Tipo="Simulacro"/Severidad="Normal". Deliberadamente NO
        agrega la zona a self._zonas_en_sabotaje: ese set solo se limpia
        cuando la camara "se destapa" de verdad, y una zona simulada nunca
        pasa por ese camino - el costo aceptado es que el resumen de la
        alarma no lista esta zona por nombre."""
        hilo = self.hilos_camara.get(zona)
        if hilo is None:
            return False
        self._puente_simulacro.disparado.emit()
        hilo.disparar_simulacro()
        return True

    def _evidencia_sabotaje_lista(self, zona, mensaje, datos_alerta, es_simulacro=False):
        self.view.registrar_evento(mensaje)
        if datos_alerta is None:
            return
        ruta_foto, hash_foto = datos_alerta
        encabezado = (
            "🧪 SIMULACRO (no es un sabotaje real)\n" if es_simulacro
            else "🚨 ALERTA: camara tapada o movida\n"
        )
        alertas_service.enviar_alerta_async(
            ruta_foto,
            f"{encabezado}"
            f"Camara: {zona}\n"
            f"Hora: {time.strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"Foto: {SEGUNDOS_FOTO_ANTES} segundos antes del sabotaje\n"
            f"Firma SHA-256: {hash_foto}",
            al_terminar=self._puente_alertas.resultado.emit,
        )

    # ---------------- captura manual de evidencia ----------------
    def capturar_evidencia(self, zona):
        hilo = self.hilos_camara.get(zona)
        camara = self.camaras_por_zona.get(zona)
        if not hilo or not camara:
            return
        frame = hilo.capturar_snapshot()
        if frame is None:
            self.view.registrar_evento(f"No hay imagen disponible en {zona} para capturar evidencia.")
            return

        marca_tiempo = time.strftime("%Y%m%d_%H%M%S")
        ruta = os.path.join(EVIDENCIAS_DIR, f"manual_{zona}_{marca_tiempo}.jpg".replace(" ", "_"))
        cv2.imwrite(ruta, frame)
        hash_archivo = firmar_archivo(ruta)
        evidencia_model.crear(
            camara["IdZona"], ruta, "Foto", hash_archivo, id_usuario=self.usuario["IdUsuario"],
        )
        self.view.registrar_evento(f"[EVIDENCIA] Captura manual en {zona} firmada SHA-256: {hash_archivo[:16]}...")

    # ---------------- ampliar zona ----------------
    def ampliar_zona(self, zona):
        if zona in self._zonas_ocultas:
            self.view.registrar_evento(f"{zona} esta oculta: muestrela primero desde \"Ocultas\" de su grupo.")
            return
        dialogo = self.dialogos_ampliados.get(zona)
        if dialogo is None:
            dialogo = ZonaAmpliadaDialog(zona, self.view)
            dialogo.linea_definida.connect(lambda p1, p2, z=zona: self._poner_linea(z, p1, p2))
            dialogo.linea_quitada.connect(lambda z=zona: self._poner_linea(z, None, None))
            dialogo.ia_alternada.connect(lambda activa, z=zona: self._alternar_ia(z, activa))
            dialogo.zona_agregada.connect(lambda nombre, pts, z=zona: self._agregar_zona(z, nombre, pts))
            dialogo.zonas_borradas.connect(lambda z=zona: self._guardar_zonas(z, []))
            dialogo.calibracion_definida.connect(lambda cam, plano, z=zona: self._guardar_calibracion(z, cam, plano))
            self.dialogos_ampliados[zona] = dialogo
        camara = self.camaras_por_zona.get(zona)
        dialogo.set_tiene_linea(bool(camara and self._leer_linea(camara["IdCamara"])))
        dialogo.ruta_plano = self._ajustes.value("mapa/plano", "") or ""
        self._refrescar_dialogo_ia(zona)
        dialogo.show()
        dialogo.raise_()

    # ---------------- IA de personas (ropa, zonas, plano) ----------------
    # todo por camara en ESTA PC (QSettings): ia/<id> = "1", zonas_ia/<id> y
    # calibracion/<id> en JSON. Los avistamientos van a evidencias/avistamientos
    SEG_ENTRE_AVISTAMIENTOS = 4.0

    def _leer_json(self, clave, defecto):
        try:
            return json.loads(self._ajustes.value(clave, "") or "null") or defecto
        except ValueError:
            return defecto

    def _encender_ia(self, hilo, id_camara):
        try:
            analizador = AnalizadorIA(al_resultado=hilo.personas_detectadas.emit)
        except Exception as e:   # sin modelo / OpenCV sin DNN: la camara sigue normal
            self.view.registrar_evento(f"[IA] No se pudo iniciar la IA de personas: {e}")
            return False
        analizador.zonas = [(n, [tuple(p) for p in pts]) for n, pts in self._leer_json(f"zonas_ia/{id_camara}", [])]
        calib = self._leer_json(f"calibracion/{id_camara}", None)
        if calib:
            analizador.homografia = calcular_homografia(calib["camara"], calib["plano"])
        hilo.ia = analizador
        return True

    def _alternar_ia(self, zona, activa):
        camara = self.camaras_por_zona.get(zona)
        hilo = self.hilos_camara.get(zona)
        if not camara:
            return
        self._ajustes.setValue(f"ia/{camara['IdCamara']}", "1" if activa else "0")
        if hilo and activa and hilo.ia is None:
            if self._encender_ia(hilo, camara["IdCamara"]):
                self.view.registrar_evento(f"[IA] Deteccion de personas activa en {camara['Nombre']}.")
        elif hilo and not activa and hilo.ia is not None:
            ia, hilo.ia = hilo.ia, None
            ia.detener()
            self.view.registrar_evento(f"[IA] Deteccion de personas apagada en {camara['Nombre']}.")
        self._refrescar_dialogo_ia(zona)

    def _agregar_zona(self, zona, nombre, puntos):
        camara = self.camaras_por_zona.get(zona)
        if not camara:
            return
        zonas = self._leer_json(f"zonas_ia/{camara['IdCamara']}", [])
        zonas = [z for z in zonas if z[0].lower() != nombre.lower()] + [[nombre, [list(p) for p in puntos]]]
        self._guardar_zonas(zona, zonas)

    def _guardar_zonas(self, zona, zonas):
        camara = self.camaras_por_zona.get(zona)
        if not camara:
            return
        self._ajustes.setValue(f"zonas_ia/{camara['IdCamara']}", json.dumps(zonas))
        hilo = self.hilos_camara.get(zona)
        if hilo and hilo.ia:
            hilo.ia.zonas = [(n, [tuple(p) for p in pts]) for n, pts in zonas]
        self.view.registrar_evento(f"[IA] {camara['Nombre']}: {len(zonas)} zona(s) con nombre.")
        self._refrescar_dialogo_ia(zona)

    def _guardar_calibracion(self, zona, puntos_camara, puntos_plano):
        camara = self.camaras_por_zona.get(zona)
        if not camara:
            return
        self._ajustes.setValue(f"calibracion/{camara['IdCamara']}",
                               json.dumps({"camara": puntos_camara, "plano": puntos_plano}))
        hilo = self.hilos_camara.get(zona)
        if hilo and hilo.ia:
            hilo.ia.homografia = calcular_homografia(puntos_camara, puntos_plano)
        self.view.registrar_evento(f"[IA] {camara['Nombre']} calibrada con el plano del lugar.")
        self._refrescar_dialogo_ia(zona)

    def _refrescar_dialogo_ia(self, zona):
        dialogo = self.dialogos_ampliados.get(zona)
        camara = self.camaras_por_zona.get(zona)
        if not dialogo or not camara:
            return
        id_cam = camara["IdCamara"]
        dialogo.set_estado_ia(
            self._ajustes.value(f"ia/{id_cam}", "") == "1",
            len(self._leer_json(f"zonas_ia/{id_cam}", [])),
            bool(self._leer_json(f"calibracion/{id_cam}", None)),
        )

    def _on_personas(self, zona, personas):
        if zona in self._zonas_ocultas:
            return
        for oyente in self.oyentes_personas:
            oyente(zona, personas)
        if not personas:
            return
        ahora = time.time()
        ultimos = self.__dict__.setdefault("_ultimo_avistamiento", {})
        if ahora - ultimos.get(zona, 0.0) < self.SEG_ENTRE_AVISTAMIENTOS:
            return   # la misma gente cuadro a cuadro: un registro cada tantos segundos
        ultimos[zona] = ahora
        nombre = self.camaras_por_zona.get(zona, {}).get("Nombre", zona)
        # escribir JPGs al disco fuera del hilo de la UI
        threading.Thread(target=avistamientos.registrar, args=(nombre, personas, ahora), daemon=True).start()
        self._alerta_silenciosa_personas(zona, nombre, personas, ahora)

    SEG_ENTRE_ALERTAS_IA = 60.0

    def _alerta_silenciosa_personas(self, zona, nombre, personas, ahora):
        """Persona detectada: queda en la bitacora y como evidencia en la BD, y
        llega al celular sin sonar (sin sirena ni voz). Una por minuto por camara."""
        ultimas = self.__dict__.setdefault("_ultima_alerta_ia", {})
        if ahora - ultimas.get(zona, 0.0) < self.SEG_ENTRE_ALERTAS_IA:
            return
        hilo = self.hilos_camara.get(zona)
        camara = self.camaras_por_zona.get(zona)
        frame = hilo.capturar_snapshot() if hilo else None
        if frame is None or not camara:
            return
        ultimas[zona] = ahora
        cantidad = len(personas)
        self.view.registrar_evento(
            f"[IA] {cantidad} persona(s) detectada(s) en {nombre} - alerta silenciosa enviada."
        )
        zonas_ia = hilo.ia.zonas if hilo.ia else None
        id_usuario = self.usuario["IdUsuario"]

        def tarea():
            marca = time.strftime("%Y%m%d_%H%M%S", time.localtime(ahora))
            ruta = os.path.join(EVIDENCIAS_DIR, f"ia_personas_{nombre}_{marca}.jpg".replace(" ", "_"))
            cv2.imwrite(ruta, dibujar_personas(frame, personas, zonas_ia))
            hash_foto = firmar_archivo(ruta)
            try:
                evidencia_model.crear(camara["IdZona"], ruta, "Foto", hash_foto, id_usuario=id_usuario)
            except Exception as e:
                self._puente_alertas.resultado.emit(False, f"No se guardo la evidencia de IA en la BD: {e}")
            ok, msg = alertas_service.enviar_alerta(
                ruta,
                f"👤 Persona detectada (IA)\n"
                f"Camara: {nombre}\n"
                f"Personas: {cantidad}\n"
                f"Hora: {time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(ahora))}\n"
                f"Firma SHA-256: {hash_foto}",
                silenciosa=True,
            )
            self._puente_alertas.resultado.emit(ok, msg)

        threading.Thread(target=tarea, daemon=True).start()

    # ---------------- linea virtual (contador de cruces) ----------------
    PAUSA_AVISO_VOZ_SEG = 4.0
    _voz_ocupada = threading.Lock()

    def _leer_linea(self, id_camara):
        """(p1, p2) en 0..1 guardada en ESTA PC (QSettings, como las ocultas), o None."""
        valor = self._ajustes.value(f"linea_virtual/{id_camara}", "")
        try:
            x1, y1, x2, y2 = (float(v) for v in str(valor).split(","))
            return (x1, y1), (x2, y2)
        except ValueError:
            return None

    def _poner_linea(self, zona, p1, p2):
        camara = self.camaras_por_zona.get(zona)
        if not camara:
            return
        clave = f"linea_virtual/{camara['IdCamara']}"
        hilo = self.hilos_camara.get(zona)
        if p1 is None:
            self._ajustes.remove(clave)
            if hilo:
                hilo.detector_linea = None
            self.view.registrar_evento(f"[LINEA] Linea virtual quitada en {zona}.")
        else:
            self._ajustes.setValue(clave, f"{p1[0]:.4f},{p1[1]:.4f},{p2[0]:.4f},{p2[1]:.4f}")
            if hilo:
                hilo.detector_linea = DetectorLinea(p1, p2)
            self.view.registrar_evento(
                f"[LINEA] Linea virtual activa en {zona}: se cuentan las personas que la cruzan."
            )
        dialogo = self.dialogos_ampliados.get(zona)
        if dialogo:
            dialogo.set_tiene_linea(p1 is not None)

    def _on_movimiento(self, zona, nivel):
        if zona in self._zonas_ocultas:
            return
        for oyente in self.oyentes_movimiento:
            oyente(zona, nivel)

    def _on_cruce_linea(self, zona, sentido, entradas, salidas):
        if zona in self._zonas_ocultas:
            return
        camara = self.camaras_por_zona.get(zona, {})
        nombre = camara.get("Nombre", zona)
        verbo = "entrando" if sentido > 0 else "saliendo"
        self.view.registrar_evento(
            f"[LINEA] Persona {verbo} en {nombre} (entran {entradas} / salen {salidas})."
        )
        zf = self.view.zona_widget(zona)
        if zf:
            zf.estado_label.setText(f"Linea virtual: entran {entradas} | salen {salidas}")
        ahora = time.time()
        if ahora - getattr(self, "_ultimo_aviso_voz", 0.0) < self.PAUSA_AVISO_VOZ_SEG:
            return  # varias personas seguidas: un aviso cada tantos segundos, no uno encima de otro
        self._ultimo_aviso_voz = ahora

        def avisar():
            # pyttsx3 no tolera dos voces a la vez: si ya esta hablando, se salta
            if self._voz_ocupada.acquire(blocking=False):
                try:
                    hablar(f"Atencion. Persona {verbo} en {nombre}.")
                finally:
                    self._voz_ocupada.release()

        threading.Thread(target=avisar, daemon=True).start()

    # ---------------- comandos (voz / manual) ----------------
    def _procesar_comando_manual(self, texto):
        accion, zona, _, numero_preset = interpretar_comando(texto, self.view.camaras_para_voz())
        resultado = self._ejecutar_comando(accion, zona, numero_preset)
        comando_model.registrar(self.usuario["IdUsuario"], texto, resultado)
        self.view.registrar_evento(f"[COMANDO] \"{texto}\" -> {resultado}")

    # ---------------- voz: mantener apretado para hablar ----------------
    def _empezar_a_hablar(self):
        if self.hilo_voz:
            return
        hilo = GrabacionVozThread(device_index=self.view.microfono_seleccionado())
        hilo.texto_reconocido.connect(self._on_texto_voz)
        hilo.texto_parcial.connect(lambda t: self.view.lbl_voz_parcial.setText(f"Detectando: \"{t}\""))
        hilo.error_reconocimiento.connect(self.view.lbl_estado_voz.setText)
        self.view.lbl_voz_parcial.setText("")
        # se guarda hasta que termine (reconocer tarda ~1 s tras soltar):
        # soltar la ultima referencia a un QThread vivo cierra la app
        self._hilos_voz_terminando.append(hilo)
        hilo.finished.connect(lambda h=hilo: self._hilos_voz_terminando.remove(h))
        hilo.finished.connect(hilo.deleteLater)
        self.hilo_voz = hilo
        hilo.start()
        self.view.lbl_estado_voz.setText("Escuchando... suelte al terminar")

    def _terminar_de_hablar(self):
        hilo, self.hilo_voz = self.hilo_voz, None
        if not hilo:
            return
        hilo.soltar()
        if hilo.isRunning():
            self.view.lbl_estado_voz.setText("Reconociendo...")

    def _on_texto_voz(self, texto):
        accion, zona, _, numero_preset = interpretar_comando(texto, self.view.camaras_para_voz())
        resultado = self._ejecutar_comando(accion, zona, numero_preset)
        comando_model.registrar(self.usuario["IdUsuario"], texto, resultado)
        self.view.lbl_voz_parcial.setText(f"Escuche: \"{texto}\"")
        self.view.lbl_estado_voz.setText(resultado)
        self.view.registrar_evento(f"[VOZ] \"{texto}\" -> {resultado}")
        threading.Thread(target=hablar, args=(resultado,), daemon=True).start()

    def _ejecutar_comando(self, accion, zona, numero_preset=None):
        zona_nombre = zona if zona in self.camaras_por_zona else None
        if accion == "ampliar" and zona_nombre in self.hilos_camara:
            self.ampliar_zona(zona_nombre)
            return f"Ampliando {zona_nombre}"
        if accion == "capturar":
            if zona_nombre in self.hilos_camara:
                self.capturar_evidencia(zona_nombre)
                return f"Evidencia capturada en {zona_nombre}"
            return "Indique la camara, por ejemplo: camara 1 capturar"
        if accion in ("zoom_in", "zoom_out", "zoom_reset"):
            if zona_nombre not in self.hilos_camara:
                return "Indique la camara, por ejemplo: camara 1 zoom"
            return self._ajustar_zoom(zona_nombre, accion)
        if accion.startswith("mover_"):
            direccion = accion.split("_", 1)[1]
            return self._mover_camara(zona_nombre, direccion)
        if accion in imou_cloud.ACCIONES:
            return self._accion_nube_imou(zona_nombre, accion)
        if accion in ("preset_guardar", "preset_ir"):
            if numero_preset is None:
                return "Indique el numero de preset (ej. \"patio preset 1\")"
            return self._usar_preset_camara(zona_nombre, numero_preset, accion.split("_", 1)[1])
        if accion == "vista_general":
            return "Mostrando vista general de las camaras"
        if accion == "ampliar":
            return "Indique la camara, por ejemplo: camara 1 ampliar"
        return "Comando no reconocido"

    def _mover_camara(self, zona, direccion):
        camara = self.camaras_por_zona.get(zona)
        if not camara:
            return "Indique una zona valida para mover la camara"
        if camara["TipoConexion"] != "RTSP":
            return f"La camara de {zona} no soporta movimiento PTZ (es USB)"
        if not camara.get("TienePTZ"):
            # capacidad declarada POR CAMARA al agregarla (pestana Camaras o
            # NVR/DVR), no asumida por marca: evita intentar ONVIF (y
            # esperar su timeout) en una camara que de entrada no tiene
            # motor, y da un mensaje claro en vez de un error tecnico
            return f"La camara de {zona} no tiene motor PTZ (no se marco al agregarla)"

        hilo = MovimientoPTZThread(camara["UrlConexion"], camara["Marca"], direccion)
        hilo.resultado.connect(lambda ok, mensaje, z=zona: self._on_resultado_ptz(ok, mensaje, z))
        hilo.finished.connect(lambda h=hilo: self._hilos_ptz_activos.remove(h))
        hilo.finished.connect(hilo.deleteLater)
        self._hilos_ptz_activos.append(hilo)  # evita que se recolecte mientras corre
        hilo.start()
        return f"Moviendo camara de {zona} hacia {direccion}..."

    def _usar_preset_camara(self, zona, numero_preset, accion_preset):
        camara = self.camaras_por_zona.get(zona)
        if not camara:
            return "Indique una zona valida para usar un preset PTZ"
        if camara["TipoConexion"] != "RTSP":
            return f"La camara de {zona} no soporta presets PTZ (es USB)"
        if not camara.get("TienePTZ"):
            return f"La camara de {zona} no tiene motor PTZ (no se marco al agregarla)"

        hilo = PresetPTZThread(camara["UrlConexion"], camara["Marca"], numero_preset, accion_preset)
        hilo.resultado.connect(lambda ok, mensaje, z=zona: self._on_resultado_ptz(ok, mensaje, z))
        hilo.finished.connect(lambda h=hilo: self._hilos_ptz_activos.remove(h))
        hilo.finished.connect(hilo.deleteLater)
        self._hilos_ptz_activos.append(hilo)  # evita que se recolecte mientras corre
        hilo.start()
        verbo = "Guardando posicion como" if accion_preset == "guardar" else "Yendo al"
        return f"{verbo} preset {numero_preset} en {zona}..."

    def _accion_nube_imou(self, zona, accion):
        """Sirena / luz / privacidad / seguimiento: solo por la nube Imou
        (la camara no los expone por ONVIF local, ver imou_cloud.py)."""
        camara = self.camaras_por_zona.get(zona)
        if not camara:
            return "Indique la camara, por ejemplo: imou sirena"
        if camara["TipoConexion"] != "RTSP" or camara["Marca"] != "Dahua":
            return f"La camara de {zona} no es Imou/Dahua: esa funcion no esta disponible"
        if not imou_cloud.configurada():
            return "Falta configurar la nube Imou (CAM_IMOU_APP_ID y CAM_IMOU_APP_SECRET)"

        host, puerto, usuario, clave = _datos_conexion(camara["UrlConexion"], camara["Marca"])
        hilo = imou_cloud.ImouCloudThread(accion, host, puerto, usuario, clave)
        hilo.resultado.connect(lambda ok, mensaje: self.view.registrar_evento(f"{'[IMOU]' if ok else '[IMOU-ERROR]'} {mensaje}"))
        hilo.finished.connect(lambda h=hilo: self._hilos_ptz_activos.remove(h))
        hilo.finished.connect(hilo.deleteLater)
        self._hilos_ptz_activos.append(hilo)  # evita que se recolecte mientras corre
        hilo.start()
        return f"{imou_cloud.DESCRIPCION[accion]} en {zona} (enviando a la nube Imou)..."

    def _on_resultado_ptz(self, ok, mensaje, zona):
        self.view.registrar_evento(f"{'[PTZ]' if ok else '[PTZ-ERROR]'} {mensaje}")
        if ok:
            # tras un movimiento el video suele verse mas distorsionado hasta
            # el proximo fotograma clave: se pide resincronizar de una vez
            hilo_camara = self.hilos_camara.get(zona)
            if hilo_camara:
                hilo_camara.forzar_reconexion()

    def _ajustar_zoom(self, zona, accion):
        actual = self.factor_zoom.get(zona, 1.0)
        if accion == "zoom_in":
            nuevo = min(3.0, actual + 0.5)
        elif accion == "zoom_out":
            nuevo = max(1.0, actual - 0.5)
        else:
            nuevo = 1.0
        self.factor_zoom[zona] = nuevo
        return f"Zoom en {zona} ajustado a x{nuevo:.1f}"

    # ---------------- panico silencioso ----------------
    def activar_panico(self):
        camara = self._camara_panico()
        if not camara:
            return
        id_incidencia = incidencia_model.crear(
            camara["IdZona"], "Panico",
            "Modo panico silencioso activado (gesto de manos arriba o boton manual)",
            id_turno=self.obtener_turno_actual(),
            severidad="Critica",
        )

        hilo = self.hilos_camara.get(camara["Clave"])
        if hilo:
            frame = hilo.capturar_snapshot()
            if frame is not None:
                marca_tiempo = time.strftime("%Y%m%d_%H%M%S")
                ruta = os.path.join(EVIDENCIAS_DIR, f"panico_{marca_tiempo}.jpg")
                cv2.imwrite(ruta, frame)
                hash_archivo = firmar_archivo(ruta)
                evidencia_model.crear(
                    camara["IdZona"], ruta, "Foto", hash_archivo,
                    id_usuario=self.usuario["IdUsuario"], id_incidencia=id_incidencia,
                )
                # la alerta al celular es precisamente el "aviso externo silencioso"
                # de la propuesta: no suena nada en el local, pero llega al celular
                alertas_service.enviar_alerta_async(
                    ruta,
                    f"🆘 MODO PANICO SILENCIOSO\nCamara: {camara['Nombre']}\n"
                    f"Hora: {time.strftime('%d/%m/%Y %H:%M:%S')}\nFirma SHA-256: {hash_archivo}",
                    al_terminar=self._puente_alertas.resultado.emit,
                )

        # sin alarma sonora: es un modo silencioso para no poner en riesgo al trabajador
        self.view.registrar_evento(
            "[PANICO SILENCIOSO] Alerta critica registrada. Evidencias protegidas: "
            "el borrado queda bloqueado por cadena de custodia."
        )

    # ---------------- fatiga (dead man's switch) ----------------
    def _pedir_confirmacion_fatiga(self):
        self.view.lbl_fatiga.setText("Confirme que sigue atento (tiene tiempo limitado)...")
        self.view.btn_confirmar.setEnabled(True)
        self.view.set_boton_confirmar_urgente(True)

    def _confirmar_fatiga(self):
        self.fatiga.confirmar()

    def _fatiga_confirmada_ok(self):
        self.view.lbl_fatiga.setText("Confirmado. Sin solicitudes pendientes.")
        self.view.btn_confirmar.setEnabled(False)
        self.view.set_boton_confirmar_urgente(False)
        fatiga_model.registrar(self.usuario["IdUsuario"], True, self.obtener_turno_actual())

    def _fatiga_detectada(self):
        self.view.lbl_fatiga.setText("FALTA DETECTADA: no se confirmo atencion a tiempo.")
        self.view.btn_confirmar.setEnabled(False)
        self.view.set_boton_confirmar_urgente(False)
        QApplication.beep()
        fatiga_model.registrar(self.usuario["IdUsuario"], False, self.obtener_turno_actual())
        camara = self._camara_panico()
        if camara:
            incidencia_model.crear(
                camara["IdZona"], "Fatiga", "Vigilante no confirmo atencion a tiempo",
                id_turno=self.obtener_turno_actual(), severidad="Alta",
            )
        self.view.registrar_evento("[FATIGA] El vigilante no confirmo a tiempo. Incidencia registrada.")

    # ---------------- apagado ----------------
    def detener(self):
        # se pide el paro de todos los hilos primero (en paralelo) y luego
        # se espera cada uno: mucho mas rapido que detener+esperar de a uno
        alarma_service.detener_sirena()
        for hilo in self.hilos_camara.values():
            hilo.detener()
        for hilo in self._hilos_voz_terminando:
            hilo.soltar()
        if self.detector_panico:
            self.detector_panico.detener()
        self.fatiga.detener()

        # una camara puede estar dentro de una apertura RTSP (hasta ~4s con
        # timeout real): se espera hasta un limite total para cerrar limpio
        # en vez de destruir un QThread vivo (eso cierra la app con error)
        limite = time.time() + 6.0
        hilos = list(self.hilos_camara.values()) + list(self.__dict__.get("_hilos_retirados", []))
        for hilo in hilos:
            hilo.detener()
            hilo.wait(max(100, int((limite - time.time()) * 1000)))
        for hilo in list(self._hilos_voz_terminando):
            hilo.wait(1500)
        if self.detector_panico:
            self.detector_panico.wait(1500)
