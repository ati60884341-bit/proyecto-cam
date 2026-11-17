"""Correr con:  python tests/test_ia_personas.py   (sin camaras; usa el modelo de app/recursos/modelos)"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import ia_personas as ia

# --- nombres de color (BGR puro dentro de un "torso") ---
for esperado, bgr in [("rojo", (30, 30, 210)), ("azul", (200, 80, 30)), ("verde", (40, 160, 40)),
                      ("amarillo", (30, 220, 230)), ("blanco", (235, 235, 235)), ("negro", (20, 20, 20)),
                      ("gris", (120, 120, 120)), ("azul oscuro", (90, 30, 20)), ("celeste", (230, 200, 90)),
                      ("rosado", (180, 110, 240)), ("morado", (160, 50, 120)), ("naranja", (20, 130, 240)),
                      ("marron", (30, 60, 110)), ("beige", (150, 190, 215)),
                      ("blanco", (235, 225, 215))]:   # blanco azulado bajo fluorescente
    img = np.full((100, 60, 3), bgr, np.uint8)
    obtenido = ia.color_ropa(img, (0, 0, 60, 100))[0]
    assert obtenido == esperado, (esperado, obtenido)

# polo rojo y pantalon azul en la misma caja
p = np.full((200, 80, 3), (70, 70, 70), np.uint8)
p[40:100] = (30, 30, 210)
p[110:180] = (200, 80, 30)
assert ia.color_ropa(p, (0, 0, 80, 200)) == ("rojo", "azul"), ia.color_ropa(p, (0, 0, 80, 200))

# --- zonas: dentro / cerca ---
zonas = [("Puerta", [(0.0, 0.0), (0.3, 0.0), (0.3, 0.4), (0.0, 0.4)]),
         ("Escritorio", [(0.6, 0.6), (1.0, 0.6), (1.0, 1.0), (0.6, 1.0)])]
assert ia.zona_de((0.1, 0.2), zonas) == ("en", "Puerta")
assert ia.zona_de((0.8, 0.9), zonas) == ("en", "Escritorio")
assert ia.zona_de((0.5, 0.8), zonas) == ("cerca", "Escritorio")
assert ia.zona_de((0.35, 0.1), zonas) == ("cerca", "Puerta")
assert ia.zona_de((0.5, 0.5), []) == (None, None)
assert ia.pies((100, 50, 200, 350), 400, 400) == (0.375, 0.875)

# --- calibracion camara -> plano ---
cam = [(0.1, 0.9), (0.9, 0.9), (0.7, 0.4), (0.3, 0.4)]      # trapecio del piso visto en perspectiva
plano = [(0.2, 0.8), (0.6, 0.8), (0.6, 0.3), (0.2, 0.3)]    # rectangulo en el plano
H = ia.calcular_homografia(cam, plano)
for c, esperado in zip(cam, plano):
    x, y = ia.a_plano(c, H)
    assert abs(x - esperado[0]) < 1e-4 and abs(y - esperado[1]) < 1e-4
x, y = ia.a_plano((0.5, 0.9), H)
assert abs(x - 0.4) < 1e-4 and abs(y - 0.8) < 1e-4

# --- detector: carga el modelo y no inventa personas en una escena vacia ---
d = ia.DetectorPersonas()
vacia = np.full((720, 1280, 3), 200, np.uint8)
assert d.detectar(vacia) == []
salida = ia.dibujar(vacia, [{"caja": (100, 100, 200, 400), "conf": 0.9, "arriba": "rojo", "abajo": "azul",
                             "relacion": "en", "zona": "Puerta"}], zonas)
assert salida.shape == vacia.shape and not np.array_equal(salida, vacia)
assert ia.describir({"arriba": "rojo", "abajo": "azul", "relacion": "cerca", "zona": "Puerta"}) == \
    "arriba rojo, abajo azul  ·  cerca de Puerta"

print("OK ia personas")
