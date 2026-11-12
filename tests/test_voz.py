"""Correr con:  python tests/test_voz.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.voice_service import buscar_camara, interpretar_comando

CAMARAS = [
    (1, "Cam-Ingreso-01"),
    (2, "DVR-PRUEBA-Hikvision-Canal1"),
    (3, "DVR-PRUEBA-Hikvision-Canal2"),
    (4, "NVR-PRUEBA-Dahua-Canal2"),
]

casos_camara = [
    ("camara 3 ampliar", "DVR-PRUEBA-Hikvision-Canal2"),
    ("cámara tres zoom", "DVR-PRUEBA-Hikvision-Canal2"),
    ("cámara número 1 foto", "Cam-Ingreso-01"),
    ("ingreso zoom", "Cam-Ingreso-01"),
    ("hikvision canal 2 capturar", "DVR-PRUEBA-Hikvision-Canal2"),
    ("dahua ampliar", "NVR-PRUEBA-Dahua-Canal2"),
    ("canal 2 ampliar", None),          # dos camaras en canal 2: no adivina
    ("hikvision ampliar", None),        # dos Hikvision: no adivina
    ("camara 9 ampliar", None),         # no existe
    ("vista general", None),
]
for texto, esperado in casos_camara:
    obtenido = buscar_camara(texto, CAMARAS)
    assert obtenido == esperado, f"{texto!r}: {obtenido!r} != {esperado!r}"

casos_accion = [
    ("ingreso zoom", "zoom_in"),
    ("camara 1 acercar", "zoom_in"),
    ("camara 1 alejar", "zoom_out"),
    ("camara 1 quitar zoom", "zoom_reset"),
    ("camara 2 ampliar", "ampliar"),
    ("camara 2 capturar", "capturar"),
    ("camara 2 mover izquierda", "mover_izquierda"),
    ("camara 2 preset 1 guardar", "preset_guardar"),
    ("vista general", "vista_general"),
]
for texto, esperada in casos_accion:
    accion = interpretar_comando(texto, CAMARAS)[0]
    assert accion == esperada, f"{texto!r}: {accion!r} != {esperada!r}"

print("OK", len(casos_camara) + len(casos_accion), "casos")
