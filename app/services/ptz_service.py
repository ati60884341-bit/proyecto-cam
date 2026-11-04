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


class PresetPTZThread(QThread):
    """Guarda o va a una posicion PTZ guardada (preset) via ONVIF - ej.
    "patio preset 1 guardar" / "patio preset 1". Los presets quedan
    grabados en la propia camara (no en esta base de datos): se
    identifican por nombre ("Preset1".."Preset9") y se buscan con
    GetPresets cada vez, porque el PresetToken que asigna cada marca/modelo
    no es predecible de antemano."""

    resultado = pyqtSignal(bool, str)

    def __init__(self, url_rtsp, marca, numero, accion, parent=None):
        super().__init__(parent)
        self.url_rtsp = url_rtsp
        self.marca = marca
        self.numero = numero
        self.accion = accion  # "guardar" | "ir"

    def run(self):
        if self.accion not in ("guardar", "ir"):
            self.resultado.emit(False, f"Accion de preset no reconocida: {self.accion}")
            return

        try:
            from onvif import ONVIFCamera
        except ImportError:
            self.resultado.emit(False, "onvif-zeep no esta instalado: no se pueden usar presets PTZ.")
            return

        host, puerto, usuario, clave = _datos_conexion(self.url_rtsp, self.marca)
        if not host or not usuario:
            self.resultado.emit(False, "La camara no tiene usuario/host ONVIF (revise la URL RTSP).")
            return

        nombre_preset = f"Preset{self.numero}"
        try:
            camara = ONVIFCamera(host, puerto, usuario, clave)
            media = camara.create_media_service()
            perfil = media.GetProfiles()[0]
            ptz = camara.create_ptz_service()

            presets_existentes = ptz.GetPresets({"ProfileToken": perfil.token})
            token_existente = next(
                (p.token for p in presets_existentes if getattr(p, "Name", None) == nombre_preset), None,
            )

            if self.accion == "guardar":
                solicitud = ptz.create_type("SetPreset")
                solicitud.ProfileToken = perfil.token
                solicitud.PresetName = nombre_preset
                if token_existente:
                    solicitud.PresetToken = token_existente  # actualiza el existente en vez de crear otro
                ptz.SetPreset(solicitud)
                self.resultado.emit(True, f"Posicion actual guardada como preset {self.numero}")
            else:
                if not token_existente:
                    self.resultado.emit(
                        False, f"No hay ningun preset {self.numero} guardado todavia en esta camara.",
                    )
                    return
                solicitud = ptz.create_type("GotoPreset")
                solicitud.ProfileToken = perfil.token
                solicitud.PresetToken = token_existente
                ptz.GotoPreset(solicitud)
                self.resultado.emit(True, f"Camara movida al preset {self.numero}")
        except Exception as exc:
            self.resultado.emit(
                False, f"No se pudo usar el preset PTZ (puerto {puerto}): {exc}",
            )
