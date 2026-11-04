import os
import threading
import time

from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from app.config import EVIDENCIAS_DIR
from app.models import zona_model, incidencia_model, evidencia_model, fatiga_model, comando_model
from app.services.camera_service import CamaraThread
from app.services.hash_service import firmar_archivo
from app.services.fatiga_service import AuditorFatiga
from app.services.voice_service import AsistenteVozThread, interpretar_comando, hablar, registrar_zona
from app.services.panic_service import DetectorPanicoThread
from app.services.ptz_service import MovimientoPTZThread
from app.services import telegram_service
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
        self.hilo_ptz = None

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

        self.hilo_voz = None
        self.detector_panico = None

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
            self._programar_arranque_nativo(lambda c=camara: self._iniciar_hilo_camara(c))

        self.fatiga = AuditorFatiga()
        self.fatiga.pedir_confirmacion.connect(self._pedir_confirmacion_fatiga)
        self.fatiga.fatiga_detectada.connect(self._fatiga_detectada)
        self.fatiga.confirmado.connect(self._fatiga_confirmada_ok)
        self.fatiga.iniciar()

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
            if self.detector_panico is not None:
                return  # ya esta activa (o activandose)
            self.view.lbl_estado_gesto.setText("Deteccion de gesto: activando...")
            self._programar_arranque_nativo(self._iniciar_detector_panico, paso_seg=self.PASO_ARRANQUE_PANICO_SEG)
        else:
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
        self.factor_zoom.setdefault(zona, 1.0)

        # si ya habia un hilo corriendo para esta zona (ej. dos camaras
        # registradas en la misma zona), se detiene antes de arrancar el
        # nuevo: evita dos hilos nativos (FFmpeg) compitiendo por el mismo
        # recuadro, lo que en la practica resulto inestable
        hilo_anterior = self.hilos_camara.get(zona)
        if hilo_anterior:
            hilo_anterior.detener()
            hilo_anterior.wait(1500)

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

    def agregar_camara(self, camara):
        """Agrega (o reemplaza) la camara de una zona en caliente, sin
        reiniciar la app. Cualquier marca: RTSP sirve para IP de cualquier
        fabricante, USB para webcams locales."""
        zona = camara["Zona"]

        self.camaras_por_zona[zona] = camara
        if zona not in self.zonas_por_nombre:
            zona_info = zona_model.obtener_por_nombre(zona)
            if zona_info:
                self.zonas_por_nombre[zona] = zona_info

        self.view.agregar_zona_frame(camara)
        self._programar_arranque_nativo(lambda c=camara: self._iniciar_hilo_camara(c))
        registrar_zona(zona)
        self.view.registrar_evento(
            f"[CAMARA] Nueva camara en {zona}: {camara['Nombre']} ({camara['Marca']}, {camara['TipoConexion']})."
        )

    def quitar_camara(self, zona):
        """Detiene y retira la camara de una zona (no se puede capturar,
        ampliar, hacer zoom ni mover mientras no se agregue otra)."""
        hilo = self.hilos_camara.pop(zona, None)
        if hilo:
            hilo.detener()
            hilo.wait(1500)
        self.camaras_por_zona.pop(zona, None)
        self.view.marcar_zona_removida(zona)
        self.view.registrar_evento(f"[CAMARA] Camara de {zona} quitada por el administrador.")

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
        factor = self.factor_zoom.get(zona, 1.0)
        if factor > 1.0:
            frame = self._aplicar_zoom(frame, factor)
        zf = self.view.zona_widget(zona)
        if zf:
            zf.mostrar_frame(frame)
        dialogo = self.dialogos_ampliados.get(zona)
        if dialogo and dialogo.isVisible():
            dialogo.mostrar_frame(frame)

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
        zf = self.view.zona_widget(zona)
        if zf:
            zf.actualizar_estado(estado)
        if estado == "sabotaje":
            self.view.registrar_evento(f"[ALERTA] Posible sabotaje detectado en {zona}.")

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
        QApplication.beep()

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
        dialogo = self.dialogos_ampliados.get(zona)
        if dialogo is None:
            dialogo = ZonaAmpliadaDialog(zona, self.view)
            self.dialogos_ampliados[zona] = dialogo
        dialogo.show()
        dialogo.raise_()

    # ---------------- comandos (voz / manual) ----------------
    def _procesar_comando_manual(self, texto):
        accion, zona, _ = interpretar_comando(texto)
        resultado = self._ejecutar_comando(accion, zona)
        comando_model.registrar(self.usuario["IdUsuario"], texto, resultado)
        self.view.registrar_evento(f"[COMANDO] \"{texto}\" -> {resultado}")

    def _alternar_voz(self, activar):
        if activar:
            if self.hilo_voz and self.hilo_voz.isRunning():
                return
            self.hilo_voz = AsistenteVozThread()
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

    def _on_comando_voz_reconocido(self, accion, zona, texto):
        resultado = self._ejecutar_comando(accion, zona)
        comando_model.registrar(self.usuario["IdUsuario"], texto, resultado)
        self.view.registrar_evento(f"[VOZ] \"{texto}\" -> {resultado}")
        threading.Thread(target=hablar, args=(resultado,), daemon=True).start()

    def _ejecutar_comando(self, accion, zona):
        zona_nombre = zona.capitalize() if zona else None
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
        if accion == "vista_general":
            return "Mostrando vista general de las zonas"
        return "Comando no reconocido"

    def _mover_camara(self, zona, direccion):
        camara = self.camaras_por_zona.get(zona)
        if not camara:
            return "Indique una zona valida para mover la camara"
        if camara["TipoConexion"] != "RTSP":
            return f"La camara de {zona} no soporta movimiento PTZ (es USB)"

        hilo = MovimientoPTZThread(camara["UrlConexion"], camara["Marca"], direccion)
        hilo.resultado.connect(lambda ok, mensaje, z=zona: self._on_resultado_ptz(ok, mensaje, z))
        hilo.finished.connect(hilo.deleteLater)
        self.hilo_ptz = hilo  # evita que se recolecte mientras corre
        hilo.start()
        return f"Moviendo camara de {zona} hacia {direccion}..."

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
        for hilo in self.hilos_camara.values():
            hilo.detener()
        if self.hilo_voz:
            self.hilo_voz.detener()
        if self.detector_panico:
            self.detector_panico.detener()
        self.fatiga.detener()

        for hilo in self.hilos_camara.values():
            hilo.wait(1500)
        if self.hilo_voz:
            self.hilo_voz.wait(1500)
        if self.detector_panico:
            self.detector_panico.wait(1500)
