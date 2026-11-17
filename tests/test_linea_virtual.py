"""Correr con:  python tests/test_linea_virtual.py   (video sintetico, sin camara)"""
import os
import sys

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.linea_virtual import DetectorLinea


def escena(x_persona=None, ancho=640, alto=360):
    """Fondo con algo de textura y una 'persona' (rectangulo claro) en x."""
    frame = np.full((alto, ancho, 3), 60, np.uint8)
    cv2.rectangle(frame, (0, 300), (ancho, alto), (90, 90, 90), -1)  # piso
    if x_persona is not None:
        cv2.rectangle(frame, (x_persona, 120), (x_persona + 50, 300), (230, 230, 230), -1)
    return frame


def caminar(detector, desde, hasta, paso):
    cruces = []
    for x in range(desde, hasta, paso):
        cruces += detector.procesar(escena(x))
    for _ in range(12):  # sale de cuadro: se olvida
        cruces += detector.procesar(escena())
    return cruces


# linea vertical en el medio del cuadro
det = DetectorLinea((0.5, 0.1), (0.5, 0.95))
for _ in range(40):
    det.procesar(escena())  # aprende el fondo vacio
assert det.total == 0, "sin movimiento no debe contar nada"

ida = caminar(det, 40, 580, 12)
assert len(ida) == 1, f"izquierda->derecha debe contar 1 cruce, conto {ida}"
vuelta = caminar(det, 580, 40, -12)
assert len(vuelta) == 1 and vuelta[0] != ida[0], f"la vuelta cuenta en el otro sentido: {ida} {vuelta}"
assert det.entradas == 1 and det.salidas == 1, (det.entradas, det.salidas)

# caminar por un costado sin llegar a la linea no cuenta
assert caminar(det, 40, 250, 12) == []

# linea corta arriba: pasar POR DEBAJO de ella no es cruzarla (segmento, no recta)
det2 = DetectorLinea((0.5, 0.0), (0.5, 0.2))
for _ in range(40):
    det2.procesar(escena())
assert caminar(det2, 40, 580, 12) == [], "pasar fuera del tramo dibujado no cuenta"

# dibujar no toca el original
f = escena(100)
copia = det.dibujar(f, resaltar=True)
assert copia.shape == f.shape and not np.array_equal(copia, f)
assert np.array_equal(f, escena(100))

print("OK linea virtual")
