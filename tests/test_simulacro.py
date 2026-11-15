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
os._exit(0)
