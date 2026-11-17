"""Correr con:  python tests/test_avistamientos.py   (carpeta temporal, no toca evidencias/)"""
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import avistamientos as av

f = av.interpretar_busqueda
assert f("persona de rojo") == {"arriba": "rojo", "abajo": None, "zona": None}
assert f("polo rojo y pantalon azul cerca de la puerta") == {"arriba": "rojo", "abajo": "azul", "zona": "puerta"}
assert f("Pantalón negro, casaca blanca en el Escritorio docente") == \
    {"arriba": "blanco", "abajo": "negro", "zona": "escritorio docente"}
assert f("jean azul oscuro") == {"arriba": None, "abajo": "azul oscuro", "zona": None}
assert f("alguien con ropa verde y gris") == {"arriba": "verde", "abajo": "gris", "zona": None}
assert f("rojos") == {"arriba": "rojo", "abajo": None, "zona": None}

carpeta = tempfile.mkdtemp()
recorte = np.full((180, 70, 3), 128, np.uint8)
av.registrar("Laboratorio", [
    {"arriba": "rojo", "abajo": "azul", "relacion": "en", "zona": "Puerta", "conf": 0.8, "recorte": recorte},
    {"arriba": "blanco", "abajo": "negro", "relacion": "cerca", "zona": "Escritorio docente", "conf": 0.7, "recorte": recorte},
    {"arriba": "verde", "abajo": "negro", "zona": None, "conf": 0.6},   # sin recorte: no se guarda
], t=1_000_000, carpeta=carpeta)
av.registrar("Pasillo", [{"arriba": "rojo", "abajo": "negro", "relacion": "en", "zona": "Puerta", "conf": 0.9,
                          "recorte": recorte}], t=1_000_100, carpeta=carpeta)

todos = av.buscar(carpeta=carpeta)
assert len(todos) == 3 and todos[0]["camara"] == "Pasillo", todos   # el mas nuevo primero
assert all(os.path.exists(a["ruta"]) for a in todos)
assert [a["camara"] for a in av.buscar(arriba="rojo", carpeta=carpeta)] == ["Pasillo", "Laboratorio"]
assert len(av.buscar(arriba="rojo", abajo="azul", carpeta=carpeta)) == 1
assert len(av.buscar(zona="escritorio", carpeta=carpeta)) == 1
assert len(av.buscar(zona="puerta", camara="Laboratorio", carpeta=carpeta)) == 1
assert av.buscar(arriba="morado", carpeta=carpeta) == []
assert av.buscar(carpeta=tempfile.mkdtemp()) == []

print("OK avistamientos")
