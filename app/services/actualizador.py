"""Busca si hay una version mas nueva publicada como GitHub Release de este
mismo repositorio, y la descarga. Sin dependencias nuevas: solo
urllib/json de la libreria estandar (igual criterio que el Radar de
camaras y el diagnostico de red)."""

import json
import os
import urllib.error
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

from app.version import VERSION

REPOSITORIO = "ati60884341-bit/proyecto-cam"
URL_ULTIMA_RELEASE = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"
TIMEOUT_SEG = 5


def _version_a_tupla(texto):
    texto = (texto or "").strip().lstrip("vV")
    partes = []
    for trozo in texto.split("."):
        numero = "".join(c for c in trozo if c.isdigit())
        partes.append(int(numero) if numero else 0)
    while len(partes) < 3:
        partes.append(0)
    return tuple(partes[:3])


def _pedir_json(url):
    peticion = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": "ProyectoCAM-actualizador"},
    )
    with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEG) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def buscar_actualizacion():
    """None si no hay actualizacion disponible - incluye los casos "no hay
    internet", "GitHub no responde" y "todavia no se publico ninguna
    release" (nunca interrumpe el login por esto). Si hay una version mas
    nueva que la instalada (VERSION) Y esa release tiene un instalador
    .exe adjunto, devuelve:
    {"version": "1.2.0", "notas": str, "url_instalador": str,
     "nombre_archivo": str, "tamano": int}"""
    try:
        datos = _pedir_json(URL_ULTIMA_RELEASE)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        return None

    version_remota = datos.get("tag_name", "")
    if _version_a_tupla(version_remota) <= _version_a_tupla(VERSION):
        return None

    instalador = next(
        (a for a in datos.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None,
    )
    if instalador is None:
        return None  # release sin instalador adjunto: no hay de donde bajarlo

    return {
        "version": version_remota.lstrip("vV"),
        "notas": datos.get("body") or "",
        "url_instalador": instalador["browser_download_url"],
        "nombre_archivo": instalador["name"],
        "tamano": instalador.get("size", 0),
    }


class HiloBuscarActualizacion(QThread):
    """Corre buscar_actualizacion() fuera del hilo de la UI: es una llamada
    de red, no debe congelar el programa ni atrasar el login mientras
    responde (o mientras se queda esperando el timeout)."""

    encontrada = pyqtSignal(dict)
    sin_novedad = pyqtSignal()

    def run(self):
        info = buscar_actualizacion()
        if info:
            self.encontrada.emit(info)
        else:
            self.sin_novedad.emit()


class HiloDescargarActualizacion(QThread):
    progreso = pyqtSignal(int, int)  # bytes leidos, bytes totales (0 si no se informo)
    terminado = pyqtSignal(str)      # ruta local del instalador ya descargado
    fallo = pyqtSignal(str)

    def __init__(self, url, destino, parent=None):
        super().__init__(parent)
        self.url = url
        self.destino = destino

    def run(self):
        try:
            peticion = urllib.request.Request(self.url, headers={"User-Agent": "ProyectoCAM-actualizador"})
            os.makedirs(os.path.dirname(self.destino), exist_ok=True)
            with urllib.request.urlopen(peticion, timeout=15) as respuesta:
                total = int(respuesta.headers.get("Content-Length") or 0)
                leidos = 0
                with open(self.destino, "wb") as archivo:
                    while True:
                        bloque = respuesta.read(256 * 1024)
                        if not bloque:
                            break
                        archivo.write(bloque)
                        leidos += len(bloque)
                        self.progreso.emit(leidos, total)
            self.terminado.emit(self.destino)
        except Exception as exc:
            self.fallo.emit(str(exc))
