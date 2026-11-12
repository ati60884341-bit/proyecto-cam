"""Pregunta a cada grabador registrado su modelo (API web con autenticacion
Digest) para mostrar en el Centro de Monitoreo si es DVR o NVR. Corre en un
hilo aparte y sin bloquear nada: si un equipo no responde, su grupo queda
con el titulo generico "Grabador"."""
import re

from PyQt6.QtCore import QThread, pyqtSignal

RUTAS_MODELO = {
    "Hikvision": "/ISAPI/System/deviceInfo",
    "Dahua": "/cgi-bin/magicBox.cgi?action=getDeviceType",
}


def tipo_desde_modelo(modelo):
    """'DS-7208HGHI-M1' + deviceType 'DVR' -> DVR; 'DHI-NVR1108HS-S3/H' -> NVR.
    XVR/HVR/HDVR (hibridos analogicos+IP) se muestran como DVR."""
    texto = (modelo or "").upper()
    if "NVR" in texto:
        return "NVR"
    if any(x in texto for x in ("DVR", "XVR", "HVR")):
        return "DVR"
    return "Grabador"


def consultar_modelo(marca, ip, usuario, clave, timeout=4.0):
    """Devuelve (tipo, modelo) o None si no se pudo consultar."""
    ruta = RUTAS_MODELO.get(marca)
    if not ruta or not ip:
        return None
    try:
        import requests
        from requests.auth import HTTPDigestAuth

        r = requests.get(f"http://{ip}{ruta}", auth=HTTPDigestAuth(usuario or "admin", clave or ""), timeout=timeout)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    if marca == "Hikvision":
        modelo = (re.search(r"<model>([^<]+)</model>", r.text) or [None, ""])[1].strip()
        tipo_dispositivo = (re.search(r"<deviceType>([^<]+)</deviceType>", r.text) or [None, ""])[1]
        return tipo_desde_modelo(f"{tipo_dispositivo} {modelo}"), modelo or None
    modelo = r.text.strip().split("=", 1)[-1].strip()  # "type=DHI-NVR1108HS-S3/H"
    return tipo_desde_modelo(modelo), modelo or None


class IdentificarGrabadoresThread(QThread):
    identificado = pyqtSignal(int, str, str)  # IdDispositivo, tipo, modelo

    def __init__(self, dispositivos, parent=None):
        super().__init__(parent)
        # copia de los datos: el hilo no toca la base de datos
        self.dispositivos = [dict(d) for d in dispositivos]

    def run(self):
        for d in self.dispositivos:
            info = consultar_modelo(d.get("Marca"), d.get("IP"), d.get("Usuario"), d.get("Clave"))
            if info:
                self.identificado.emit(d["IdDispositivo"], info[0], info[1] or "")
