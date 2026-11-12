"""Correr con:  python tests/test_sabotaje.py   (no usa la camara: cuadros sinteticos)"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import camera_service
from app.services.camera_service import CamaraThread


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class CapturaFalsa:
    def set(self, *_):
        return True


def escena(brillo=74):
    """Cuarto con poca luz: poco contraste pero con objetos (bordes)."""
    rng = np.random.default_rng(1)
    img = np.full((480, 640), brillo - 20, np.float32)
    img[100:300, 80:260] += 45
    img[220:420, 360:600] += 30
    img += rng.normal(0, 4, img.shape)
    gris = np.clip(img, 0, 255).astype(np.uint8)
    return np.dstack([gris] * 3)


TAPADA = np.dstack([np.full((480, 640), 4, np.uint8)] * 3)


def nuevo_hilo():
    hilo = CamaraThread(1, "w", "w", "USB", "0")
    estados = []
    hilo.estado_cambiado.connect(estados.append)
    return hilo, estados


def pasar(hilo, reloj, frame, segundos, fps=12):
    for _ in range(int(segundos * fps)):
        reloj.t += 1 / fps
        hilo._actualizar_sabotaje(frame)


import time as _time

tiempo_real = _time.time
reloj = Reloj()
camera_service.time.time = reloj  # es el modulo time global: se restaura en el caso 4

# 1) la webcam entrega un cuadro negro al encender y despues la escena normal:
#    no debe quedar "tapada" para siempre; al taparla de verdad, si alarma
hilo, estados = nuevo_hilo()
hilo._iniciar_aprendizaje()
pasar(hilo, reloj, TAPADA, 0.2)
pasar(hilo, reloj, escena(), 5)
assert "sabotaje" not in estados, f"falsa alarma al encender: {estados}"
pasar(hilo, reloj, TAPADA, 1)
assert estados.count("sabotaje") == 1, f"no detecto la camara tapada: {estados}"

# 2) el ajuste de exposicion cambia el brillo: no debe trabar el detector
hilo, estados = nuevo_hilo()
hilo._exposicion, hilo._ganancia = -4, 76
hilo._iniciar_aprendizaje()
pasar(hilo, reloj, escena(60), 5)
hilo._poner_exposicion(CapturaFalsa(), -3)
pasar(hilo, reloj, escena(80), 5)
assert "sabotaje" not in estados, f"falsa alarma por la exposicion: {estados}"
pasar(hilo, reloj, TAPADA, 1)
assert estados.count("sabotaje") == 1, f"no detecto tras cambiar exposicion: {estados}"

# 3) al destapar vuelve a normal, y una segunda tapada (pasado el enfriamiento) vuelve a alarmar
pasar(hilo, reloj, escena(80), 16)
assert estados[-1] == "conectada", estados
pasar(hilo, reloj, TAPADA, 1)
assert estados.count("sabotaje") == 2, f"la segunda tapada no alarmo: {estados}"

# 4) guardar la evidencia (8 s de video) no debe frenar la lectura de la camara
import cv2

_time.time = tiempo_real
camera_service.EVIDENCIAS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidencias")
hilo, estados = nuevo_hilo()
evidencias = []
hilo.sabotaje_detectado.connect(lambda *a: evidencias.append(a))
jpg = cv2.imencode(".jpg", escena())[1]
hilo._buffer.extend([jpg] * hilo._buffer.maxlen)
hilo._baseline_brillo, hilo._baseline_bordes = 74.0, 1.0
inicio = _time.perf_counter()
hilo._actualizar_sabotaje(TAPADA)
hilo._actualizar_sabotaje(TAPADA)
demora_ms = (_time.perf_counter() - inicio) * 1000
assert estados == ["sabotaje"], estados
assert demora_ms < 150, f"la deteccion freno la lectura de la camara {demora_ms:.0f} ms"
from PyQt6.QtCore import QCoreApplication

aplicacion = QCoreApplication.instance() or QCoreApplication([])
limite = _time.time() + 15
while not evidencias and _time.time() < limite:
    aplicacion.processEvents()  # la senal llega desde el hilo de la evidencia
    _time.sleep(0.05)
assert evidencias, "la evidencia no se guardo"
for ruta in evidencias[0][1:]:
    assert os.path.getsize(ruta) > 0
    os.remove(ruta)

print("OK sabotaje: 4 casos")
