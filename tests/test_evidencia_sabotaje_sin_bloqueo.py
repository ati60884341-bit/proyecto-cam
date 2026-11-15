"""Correr con:  python tests/test_evidencia_sabotaje_sin_bloqueo.py

El hash SHA-256 y los INSERT de evidencia de un sabotaje se movieron a un
hilo aparte (antes corrian en el slot de la senal, en el hilo de la UI).
Este test simula una base lenta y un archivo real, y confirma que arrancar
el hilo no frena al llamador."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from app.controllers.monitoreo_controller import _GuardarEvidenciaSabotajeThread
from app.models import evidencia_model, incidencia_model

aplicacion = QApplication.instance() or QApplication(sys.argv)

DEMORA_SIMULADA_SEG = 0.3
LIMITE_DEMORA_LLAMADOR_MS = 50

carpeta = tempfile.mkdtemp()
ruta_foto = os.path.join(carpeta, "foto.jpg")
ruta_video = os.path.join(carpeta, "video.avi")
with open(ruta_foto, "wb") as f:
    f.write(b"contenido de prueba" * 100)
with open(ruta_video, "wb") as f:
    f.write(b"contenido de prueba video" * 100)


def _crear_incidencia_lento(*a, **k):
    time.sleep(DEMORA_SIMULADA_SEG)
    return 1


def _crear_evidencia_lento(*a, **k):
    time.sleep(DEMORA_SIMULADA_SEG)
    return 1


original_incidencia = incidencia_model.crear
original_evidencia = evidencia_model.crear
incidencia_model.crear = _crear_incidencia_lento
evidencia_model.crear = _crear_evidencia_lento
try:
    resultado = []
    camara_info = {"IdZona": 1, "IdCamara": 1}
    hilo = _GuardarEvidenciaSabotajeThread("zona1", camara_info, ruta_video, ruta_foto, 1, 1)
    hilo.listo.connect(lambda *a: resultado.append(a))
    inicio = time.perf_counter()
    hilo.start()
    demora_ms = (time.perf_counter() - inicio) * 1000
    assert demora_ms < LIMITE_DEMORA_LLAMADOR_MS, f"_GuardarEvidenciaSabotajeThread.start() freno al llamador {demora_ms:.0f} ms"

    limite = time.time() + 5
    while not resultado and time.time() < limite:
        aplicacion.processEvents()
        time.sleep(0.02)
finally:
    incidencia_model.crear = original_incidencia
    evidencia_model.crear = original_evidencia

assert resultado, "no llego el resultado del guardado de evidencia"
zona, mensaje, datos_alerta, es_simulacro = resultado[0]
assert zona == "zona1"
assert es_simulacro is False
assert mensaje.startswith("[EVIDENCIA] Sabotaje en zona1"), mensaje  # el camino real no cambia
assert "firmados con SHA-256" in mensaje
assert datos_alerta is not None and datos_alerta[0] == ruta_foto and datos_alerta[1]
hilo.wait(2000)
print("OK: guardar evidencia de sabotaje no bloquea el hilo de la UI")
sys.stdout.flush()
os._exit(0)  # el QThread deja algo vivo que traba la salida normal del interprete
