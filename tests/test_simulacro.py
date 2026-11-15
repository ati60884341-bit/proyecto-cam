"""Correr con:  python tests/test_simulacro.py

CamaraThread.disparar_simulacro() reutiliza el pipeline de exportacion de
evidencia de sabotaje para un disparo manual de demo, en un hilo de fondo
real (igual que la deteccion real de sabotaje). La senal sabotaje_detectado
gana un 4to parametro es_simulacro para distinguir ambos casos."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
from PySide6.QtWidgets import QApplication
from app.services.camera_service import CamaraThread

aplicacion = QApplication.instance() or QApplication([])
hilo = CamaraThread(1, "zona1", "zona1", "USB", "0")
jpg = cv2.imencode(".jpg", np.zeros((10, 10, 3), np.uint8))[1]  # ndarray, igual que el buffer real (linea ~566)
hilo._buffer.append(jpg)
hilo._ultimo_frame = np.zeros((10, 10, 3), np.uint8)

resultado = []
hilo.sabotaje_detectado.connect(lambda *args: resultado.append(args))
hilo.disparar_simulacro()

limite = time.time() + 5
while not resultado and time.time() < limite:
    aplicacion.processEvents()
    time.sleep(0.02)

assert resultado, "no llego la señal sabotaje_detectado"
zona, ruta_video, ruta_foto, es_simulacro = resultado[0]
assert zona == "zona1" and es_simulacro is True
print("OK: disparar_simulacro")

# --- Tarea 12: _on_sabotaje(es_simulacro=True) debe registrar Tipo="Simulacro" ---
from unittest.mock import MagicMock
from app.controllers.monitoreo_controller import MonitoreoController
from app.models import incidencia_model

capturado_t12 = {}


def _crear_incidencia_stub_t12(id_zona, tipo, descripcion, **kwargs):
    capturado_t12["tipo"] = tipo
    capturado_t12["severidad"] = kwargs.get("severidad")
    return 1


# se evita el __init__ real (arranca sirena/QSoundEffect, hilos de camara,
# AuditorFatiga, etc. - innecesario y deja cosas vivas que traban la salida
# del proceso); solo necesitamos lo que _on_sabotaje de verdad usa
controller = MonitoreoController.__new__(MonitoreoController)
controller.view = MagicMock()
controller.usuario = {"IdUsuario": 1}
controller.obtener_turno_actual = lambda: 1
controller.camaras_por_zona = {"zona1": {"IdZona": 1, "IdCamara": 1}}

original_crear_t12 = incidencia_model.crear
incidencia_model.crear = _crear_incidencia_stub_t12
try:
    controller._on_sabotaje("zona1", "video.avi", "foto.jpg", True)
    limite = time.time() + 5
    while "tipo" not in capturado_t12 and time.time() < limite:
        aplicacion.processEvents()
        time.sleep(0.02)
finally:
    incidencia_model.crear = original_crear_t12

assert capturado_t12.get("tipo") == "Simulacro", capturado_t12
assert capturado_t12.get("severidad") == "Normal", capturado_t12
print("OK: _on_sabotaje con es_simulacro=True registra Tipo=Simulacro")

os._exit(0)
