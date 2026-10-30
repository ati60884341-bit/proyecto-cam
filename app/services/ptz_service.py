import time
from urllib.parse import urlparse

from PyQt6.QtCore import QThread, pyqtSignal

# puerto ONVIF: TP-Link Tapo usa 2020 (no el 80/8080 "estandar" de otras marcas)
PUERTOS_ONVIF_POR_MARCA = {
    "Tapo": 2020,
}
PUERTO_ONVIF_POR_DEFECTO = 80

VELOCIDAD = 0.5
DURACION_MOVIMIENTO_SEG = 1.0

DIRECCIONES = {
    "izquierda": (-VELOCIDAD, 0.0),
    "derecha": (VELOCIDAD, 0.0),
    "arriba": (0.0, VELOCIDAD),
    "abajo": (0.0, -VELOCIDAD),
}


def _datos_conexion(url_rtsp, marca):
    partes = urlparse(url_rtsp)
    puerto = PUERTOS_ONVIF_POR_MARCA.get(marca, PUERTO_ONVIF_POR_DEFECTO)
    return partes.hostname, puerto, partes.username, partes.password


class MovimientoPTZThread(QThread):
    """Mueve una camara PTZ real (Pan/Tilt/Zoom) via ONVIF - ej. la Tapo
    C510W, que tiene motor de giro. Las llamadas ONVIF son SOAP bloqueantes,
    por eso corren en su propio hilo y nunca en el hilo de la UI."""

    resultado = pyqtSignal(bool, str)

    def __init__(self, url_rtsp, marca, direccion, parent=None):
        super().__init__(parent)
        self.url_rtsp = url_rtsp
        self.marca = marca
        self.direccion = direccion

    def run(self):
        if self.direccion not in DIRECCIONES:
            self.resultado.emit(False, f"Direccion no reconocida: {self.direccion}")
            return

        try:
            from onvif import ONVIFCamera
        except ImportError:
            self.resultado.emit(False, "onvif-zeep no esta instalado: no se puede mover la camara.")
            return

        host, puerto, usuario, clave = _datos_conexion(self.url_rtsp, self.marca)
        if not host or not usuario:
            self.resultado.emit(False, "La camara no tiene usuario/host ONVIF (revise la URL RTSP).")
            return

        try:
            camara = ONVIFCamera(host, puerto, usuario, clave)
            media = camara.create_media_service()
            perfil = media.GetProfiles()[0]
            ptz = camara.create_ptz_service()

            x, y = DIRECCIONES[self.direccion]
            solicitud = ptz.create_type("ContinuousMove")
            solicitud.ProfileToken = perfil.token
            solicitud.Velocity = {"PanTilt": {"x": x, "y": y}}
            ptz.ContinuousMove(solicitud)

            time.sleep(DURACION_MOVIMIENTO_SEG)

            ptz.Stop({"ProfileToken": perfil.token})
            self.resultado.emit(True, f"Camara movida hacia {self.direccion}")
        except Exception as exc:
            self.resultado.emit(
                False,
                f"No se pudo mover la camara via ONVIF (puerto {puerto}): {exc}",
            )
