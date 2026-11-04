from app.services.radar_service import RadarEscaneoThread, ReintentoCredencialesThread


class RadarController:
    """Pestana "Radar de camaras": busca equipos en la red (ONVIF
    WS-Discovery + barrido de puerto 554 opcional) y, con un clic, lleva el
    hallazgo elegido a la pestana "Camaras" o "NVR / DVR" ya precargado.

    No pasa por la cola de arranque nativo (_programar_arranque_nativo) de
    MonitoreoController: a diferencia de FFmpeg/mediapipe, ONVIF/zeep son
    solo llamadas de red (no cargan ninguna libreria nativa pesada), igual
    que MovimientoPTZThread/PresetPTZThread en ptz_service.py, que tampoco
    pasan por esa cola."""

    def __init__(self, view, camaras_view, dvr_view, mostrar_seccion):
        self.view = view
        self.camaras_view = camaras_view
        self.dvr_view = dvr_view
        self.mostrar_seccion = mostrar_seccion
        self._hilo = None
        self._hilo_reintento = None

        self.view.escanear_solicitado.connect(self.escanear)
        self.view.reintentar_solicitado.connect(self.reintentar)
        self.view.usar_en_camaras_solicitado.connect(self.usar_en_camaras)
        self.view.usar_en_dvr_solicitado.connect(self.usar_en_dvr)

    def escanear(self, datos):
        self.view.set_escaneando(True)
        self._hilo = RadarEscaneoThread(
            escaneo_completo=datos["escaneo_completo"], usuario=datos["usuario"], clave=datos["clave"],
        )
        self._hilo.progreso.connect(self.view.actualizar_progreso)
        self._hilo.dispositivo_encontrado.connect(self.view.agregar_dispositivo)
        self._hilo.terminado.connect(self._al_terminar)
        self._hilo.start()

    def _al_terminar(self, total):
        self.view.set_escaneando(False)

    def reintentar(self, datos):
        self.view.actualizar_progreso(f"Reintentando {datos['ip']} con las credenciales indicadas...")
        self._hilo_reintento = ReintentoCredencialesThread(
            datos["ip"], usuario=datos["usuario"], clave=datos["clave"],
        )
        self._hilo_reintento.resultado.connect(self._al_reintentar)
        self._hilo_reintento.start()

    def _al_reintentar(self, info):
        self.view.agregar_dispositivo(info)
        self.view.actualizar_progreso(f"{info['ip']}: {info['marca']} {info['modelo']}".strip())

    def usar_en_camaras(self, info):
        self.camaras_view.prellenar_desde_radar(info)
        self.mostrar_seccion("camaras")

    def usar_en_dvr(self, info):
        self.dvr_view.prellenar_desde_radar(info)
        self.mostrar_seccion("dvr")
