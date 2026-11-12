import os
import threading
import time

from PyQt6.QtCore import QTimer, QObject, QSettings, pyqtSignal
from PyQt6.QtWidgets import QApplication

from app.config import EVIDENCIAS_DIR
from app.models import zona_model, incidencia_model, evidencia_model, fatiga_model, comando_model, dispositivo_dvr_model
from app.services.camera_service import CamaraThread
from app.services.grabador_info import IdentificarGrabadoresThread
from app.services.hash_service import firmar_archivo
from app.services.fatiga_service import AuditorFatiga
from app.services.voice_service import AsistenteVozThread, interpretar_comando, hablar, registrar_zona, normalizar
from app.services.panic_service import DetectorPanicoThread
from app.services.ptz_service import MovimientoPTZThread, PresetPTZThread
from app.services import telegram_service, alarma_service
from app.views.UI.zona_ampliada_dialog import ZonaAmpliadaDialog

import cv2


class _PuenteTelegram(QObject):
    """telegram_service envia desde un hilo Python comun (no QThread); una
    senal Qt es la forma segura de volver al hilo de la UI para actualizar
    la bitacora sin tocar widgets desde otro hilo."""
    resultado = pyqtSignal(bool, str)


class MonitoreoController:
    def __init__(self, dashboard_view, usuario, camaras, obtener_turno_actual):
        self.view = dashboard_view
        self.usuario = usuario
        self.obtener_turno_actual = obtener_turno_actual

        self.zonas_por_nombre = {z["Nombre"]: z for z in zona_model.listar()}
        self.camaras_por_zona = {c["Zona"]: c for c in camaras}
        self.hilos_camara = {}
        self.dialogos_ampliados = {}
        self.factor_zoom = {}
        # lista, no una sola variable: si se mueven dos camaras (zonas
        # distintas) casi al mismo tiempo, una sola variable pierde la
        # referencia a la primera mientras todavia esta corriendo (riesgo
        # de que Python la recolecte a mitad de la llamada ONVIF)
        self._hilos_ptz_activos = []

        self._puente_telegram = _PuenteTelegram()
        self._puente_telegram.resultado.connect(
            lambda ok, msg: self.view.registrar_evento(f"[TELEGRAM] {msg}")
        )

        self.view.capturar_evidencia.connect(self.capturar_evidencia)
        self.view.ampliar_zona.connect(self.ampliar_zona)
        self.view.reconectar_zona.connect(self.reconectar_camara)
        self.view.comando_manual_enviado.connect(self._procesar_comando_manual)
        self.view.asistente_voz_alternado.connect(self._alternar_voz)
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
        self._zonas_ocultas = {c["Zona"] for c in camaras if c["IdCamara"] in self._ids_ocultos}
        for zona in self._zonas_ocultas:
            self.view.set_zona_oculta(zona, True)

        # sirena de camara tapada: suena mientras haya alguna zona en
        # sabotaje; se apaga sola al destaparlas, con el boton, o al llegar
        # al tiempo maximo (para no sonar toda la noche si nadie esta)
        self._zonas_en_sabotaje = set()
        self._alarma_sonando = False
        self._timer_alarma = QTimer()
        self._timer_alarma.setSingleShot(True)
        self._timer_alarma.timeout.connect(lambda: self._silenciar_alarma("paso el tiempo maximo de 60 s"))

        self.hilo_voz = None
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
            if camara["Zona"] in self._zonas_ocultas:
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
            if "Ingreso" in self.hilos_camara:
                try:
                    self.hilos_camara["Ingreso"].frame_listo.disconnect(self.detector_panico.alimentar_frame)
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
            lambda: self.view.lbl_estado_gesto.setText("Deteccion de gesto: activa en camara de Ingreso")
        )
        self.detector_panico.progreso.connect(self._actualizar_progreso_gesto)
        if "Ingreso" in self.hilos_camara:
            self.hilos_camara["Ingreso"].frame_listo.connect(self.detector_panico.alimentar_frame)
        self.detector_panico.start()

    # ---------------- alta de camaras (cualquier marca) ----------------
    def _iniciar_hilo_camara(self, camara):
        zona = camara["Zona"]
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
        self.hilos_camara[zona] = hilo
        hilo.start()
        if zona == "Ingreso" and getattr(self, "detector_panico", None):
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
        except TypeError:
            pass
        if hilo.wait(1500):
            return
        retirados = self.__dict__.setdefault("_hilos_retirados", [])
        retirados.append(hilo)
        hilo.finished.connect(lambda h=hilo: h in retirados and retirados.remove(h))

    def agregar_camara(self, camara):
        """Agrega (o reemplaza) la camara de una zona en caliente, sin
        reiniciar la app. Cualquier marca: RTSP sirve para IP de cualquier
        fabricante, USB para webcams locales."""
        zona = camara["Zona"]

        self.camaras_por_zona[zona] = camara
        # una camara recien agregada siempre se muestra
        self._zonas_ocultas.discard(zona)
        if camara["IdCamara"] in self._ids_ocultos:
            self._ids_ocultos.discard(camara["IdCamara"])
            self._guardar_ids_ocultos()
        if zona not in self.zonas_por_nombre:
            zona_info = zona_model.obtener_por_nombre(zona)
            if zona_info:
                self.zonas_por_nombre[zona] = zona_info

        self.view.agregar_zona_frame(camara)
        self._programar_arranque_nativo(lambda c=camara: self._iniciar_hilo_camara(c))
        registrar_zona(zona)
        self._actualizar_manual_ptz()
        self.view.registrar_evento(
            f"[CAMARA] Nueva camara en {zona}: {camara['Nombre']} ({camara['Marca']}, {camara['TipoConexion']})."
        )
        if camara.get("IdDispositivo"):
            self._identificar_grabadores([camara["IdDispositivo"]])

    def quitar_camara(self, zona):
        """Detiene la camara y borra la zona por completo del Centro de
        Monitoreo: no debe quedar rastro (ni el recuadro, ni la vista
        ampliada si estaba abierta) hasta que se agregue una camara nueva."""
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
        self.view.registrar_evento(f"[CAMARA] Camara de {zona} quitada por el administrador.")

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
        dispositivos = [d for d in (dispositivo_dvr_model.obtener(i) for i in ids) if d]
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
    def _on_sabotaje(self, zona, ruta_video, ruta_foto):
        zona_info = self.zonas_por_nombre.get(zona)
        camara_info = self.camaras_por_zona.get(zona)
        if not zona_info:
            return

        id_incidencia = incidencia_model.crear(
            zona_info["IdZona"], "Sabotaje",
            "Camara tapada/movida - deteccion automatica (buffer de 8s exportado)",
            id_camara=camara_info["IdCamara"] if camara_info else None,
            id_turno=self.obtener_turno_actual(),
            severidad="Alta",
        )

        hash_foto = None
        for ruta, tipo in [(ruta_foto, "Foto"), (ruta_video, "Video")]:
            if os.path.exists(ruta):
                hash_archivo = firmar_archivo(ruta)
                if tipo == "Foto":
                    hash_foto = hash_archivo
                evidencia_model.crear(
                    zona_info["IdZona"], ruta, tipo, hash_archivo,
                    id_usuario=self.usuario["IdUsuario"], id_incidencia=id_incidencia,
                )

        self.view.registrar_evento(
            f"[EVIDENCIA] Sabotaje en {zona}: foto y video (8s previos) firmados con SHA-256 y guardados."
        )
        # (el sonido ya lo da la sirena, que arranca en _on_estado apenas se
        # detecta, sin esperar a que se exporte la evidencia)

        if os.path.exists(ruta_foto) and hash_foto:
            telegram_service.enviar_foto_async(
                ruta_foto,
                f"🚨 SABOTAJE detectado en {zona}\nSHA-256: {hash_foto}",
                al_terminar=self._puente_telegram.resultado.emit,
            )

    # ---------------- captura manual de evidencia ----------------
    def capturar_evidencia(self, zona):
        hilo = self.hilos_camara.get(zona)
        zona_info = self.zonas_por_nombre.get(zona)
        if not hilo or not zona_info:
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
            zona_info["IdZona"], ruta, "Foto", hash_archivo, id_usuario=self.usuario["IdUsuario"],
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
            self.dialogos_ampliados[zona] = dialogo
        dialogo.show()
        dialogo.raise_()

    # ---------------- comandos (voz / manual) ----------------
    def _procesar_comando_manual(self, texto):
        accion, zona, _, numero_preset = interpretar_comando(texto)
        resultado = self._ejecutar_comando(accion, zona, numero_preset)
        comando_model.registrar(self.usuario["IdUsuario"], texto, resultado)
        self.view.registrar_evento(f"[COMANDO] \"{texto}\" -> {resultado}")

    def _alternar_voz(self, activar):
        if activar:
            if self.hilo_voz and self.hilo_voz.isRunning():
                return
            self.hilo_voz = AsistenteVozThread(device_index=self.view.microfono_seleccionado())
            self.hilo_voz.comando_reconocido.connect(self._on_comando_voz_reconocido)
            self.hilo_voz.error_reconocimiento.connect(
                lambda msg: self.view.lbl_estado_voz.setText(f"Asistente: {msg}")
            )
            self.hilo_voz.escuchando.connect(
                lambda s: self.view.lbl_estado_voz.setText("Asistente escuchando..." if s else "Asistente activo")
            )
            self.hilo_voz.start()
        else:
            if self.hilo_voz:
                # no se bloquea la UI esperando: puede tardar unos segundos en
                # terminar el listen() en curso; se limpia sola al finalizar
                self.hilo_voz.detener()
                self.hilo_voz.finished.connect(self.hilo_voz.deleteLater)
                self.hilo_voz = None
            self.view.lbl_estado_voz.setText("Asistente apagado")

    def _on_comando_voz_reconocido(self, accion, zona, texto, numero_preset):
        resultado = self._ejecutar_comando(accion, zona, numero_preset)
        comando_model.registrar(self.usuario["IdUsuario"], texto, resultado)
        self.view.registrar_evento(f"[VOZ] \"{texto}\" -> {resultado}")
        threading.Thread(target=hablar, args=(resultado,), daemon=True).start()

    def _resolver_zona(self, zona_dicha):
        """zona_dicha ya viene normalizada (minusculas, sin tildes) desde
        voice_service.interpretar_comando(). Las zonas reales (claves de
        self.camaras_por_zona/self.hilos_camara) guardan su capitalizacion
        original tal cual quedo en la base de datos - "Ingreso", pero
        tambien "DVR Patio Central Canal 1" para los canales de un
        grabador. Un simple .capitalize() solo funciona con zonas de una
        palabra; esto compara normalizado contra el nombre real y punto."""
        if not zona_dicha:
            return None
        objetivo = normalizar(zona_dicha)
        return next((z for z in self.camaras_por_zona if normalizar(z) == objetivo), None)

    def _ejecutar_comando(self, accion, zona, numero_preset=None):
        zona_nombre = self._resolver_zona(zona)
        if accion == "ampliar" and zona_nombre in self.hilos_camara:
            self.ampliar_zona(zona_nombre)
            return f"Ampliando {zona_nombre}"
        if accion == "capturar":
            if zona_nombre in self.hilos_camara:
                self.capturar_evidencia(zona_nombre)
                return f"Evidencia capturada en {zona_nombre}"
            return "Indique una zona valida para capturar evidencia"
        if accion in ("zoom_in", "zoom_out", "zoom_reset"):
            if zona_nombre not in self.hilos_camara:
                return "Indique una zona valida para hacer zoom"
            return self._ajustar_zoom(zona_nombre, accion)
        if accion.startswith("mover_"):
            direccion = accion.split("_", 1)[1]
            return self._mover_camara(zona_nombre, direccion)
        if accion in ("preset_guardar", "preset_ir"):
            if numero_preset is None:
                return "Indique el numero de preset (ej. \"patio preset 1\")"
            return self._usar_preset_camara(zona_nombre, numero_preset, accion.split("_", 1)[1])
        if accion == "vista_general":
            return "Mostrando vista general de las zonas"
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
        zona_info = self.zonas_por_nombre.get("Ingreso")
        if not zona_info:
            return
        id_incidencia = incidencia_model.crear(
            zona_info["IdZona"], "Panico",
            "Modo panico silencioso activado (gesto de manos arriba o boton manual)",
            id_turno=self.obtener_turno_actual(),
            severidad="Critica",
        )

        hilo = self.hilos_camara.get("Ingreso")
        if hilo:
            frame = hilo.capturar_snapshot()
            if frame is not None:
                marca_tiempo = time.strftime("%Y%m%d_%H%M%S")
                ruta = os.path.join(EVIDENCIAS_DIR, f"panico_{marca_tiempo}.jpg")
                cv2.imwrite(ruta, frame)
                hash_archivo = firmar_archivo(ruta)
                evidencia_model.crear(
                    zona_info["IdZona"], ruta, "Foto", hash_archivo,
                    id_usuario=self.usuario["IdUsuario"], id_incidencia=id_incidencia,
                )
                # la alerta a Telegram es precisamente el "aviso externo silencioso"
                # de la propuesta: no suena nada en el local, pero llega al celular
                telegram_service.enviar_foto_async(
                    ruta,
                    f"🆘 MODO PANICO SILENCIOSO activado en Ingreso\nSHA-256: {hash_archivo}",
                    al_terminar=self._puente_telegram.resultado.emit,
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
        zona_info = self.zonas_por_nombre.get("Ingreso")
        if zona_info:
            incidencia_model.crear(
                zona_info["IdZona"], "Fatiga", "Vigilante no confirmo atencion a tiempo",
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
        if self.hilo_voz:
            self.hilo_voz.detener()
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
        if self.hilo_voz:
            self.hilo_voz.wait(1500)
        if self.detector_panico:
            self.detector_panico.wait(1500)
