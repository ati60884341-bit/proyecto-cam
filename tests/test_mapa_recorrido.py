"""Correr con:  python tests/test_mapa_recorrido.py   (sin camaras ni Qt)"""
import os
import sys

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.mapa_service import MedidorMovimiento, RecorridoMapa


def recorrer(r, eventos):
    """eventos: [(t, clave, nivel)] -> lista de pasos detectados"""
    pasos = []
    for t, clave, nivel in eventos:
        p = r.actualizar(clave, nivel, t)
        if p:
            pasos.append(p)
    return pasos


# persona: patio (t=0..5) -> pasillo (t=8..12) -> puerta (t=14..16)
r = RecorridoMapa()
ev = []
for i in range(0, 60):
    t = i * 0.5
    ev.append((t, "patio", 0.05 if t <= 5 else 0.0))
    ev.append((t, "pasillo", 0.05 if 8 <= t <= 12 else 0.0))
    ev.append((t, "puerta", 0.05 if 14 <= t <= 16 else 0.0))
pasos = recorrer(r, ev)
assert pasos == [("patio", "pasillo"), ("pasillo", "puerta")], pasos
assert r.flujos == {("patio", "pasillo"): 1, ("pasillo", "puerta"): 1}
# calor ~ segundos con movimiento (+ el 1.5 s de "apagado")
assert 5 <= r.calor["patio"] <= 7.5, r.calor
assert r.calor["patio"] > r.calor["puerta"], r.calor
assert r.activas() == set(), r.activas()

# movimiento que sigue en la misma camara no es un paso
r2 = RecorridoMapa()
assert recorrer(r2, [(t * 0.5, "patio", 0.05) for t in range(40)]) == []

# demasiado tiempo entre una camara y otra: no se une como recorrido
r3 = RecorridoMapa()
ev3 = [(t, "patio", 0.05 if t < 2 else 0.0) for t in range(0, 40)]
ev3 += [(40, "pasillo", 0.05)]
assert recorrer(r3, ev3) == []

# ruido bajo el umbral no enciende nada
r4 = RecorridoMapa()
assert recorrer(r4, [(t, "patio", 0.003) for t in range(10)]) == [] and r4.activas() == set()

# medidor: quieto ~0, con un objeto moviendose > umbral
m = MedidorMovimiento()
fondo = np.full((360, 640, 3), 70, np.uint8)
for _ in range(30):
    assert m.medir(fondo) < 0.005
niveles = []
for x in range(40, 500, 20):
    f = fondo.copy()
    cv2.rectangle(f, (x, 100), (x + 60, 300), (230, 230, 230), -1)
    niveles.append(m.medir(f))
assert max(niveles) > 0.03, max(niveles)

print("OK mapa recorrido")
