"""Correr con:  python tests/test_api_service.py

Prueba de punta a punta de la API chica para la app de Android: arranca el
servidor real (como lo hace AppController), hace login con la cuenta demo y
pega a /camaras, /incidencias y /resumen con el token."""
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import api_service

PUERTO = 8766  # distinto del real (8765) para no chocar con una app abierta
BASE = f"http://127.0.0.1:{PUERTO}"


class _HiloFalso:
    def obtener_ultimo_jpeg(self):
        import cv2
        import numpy as np

        return cv2.imencode(".jpg", np.zeros((4, 4, 3), np.uint8))[1].tobytes()


class _MonitoreoFalso:
    _alarma_sonando = False
    hilos_camara = {"Cam-Ingreso-01": _HiloFalso()}

    def estado_camaras(self):
        return [{"zona": "Cam-Ingreso-01", "nombre": "Cam-Ingreso-01", "en_linea": True, "en_sabotaje": False}]

    def resumen_camaras(self):
        return 1, 3


api_service.iniciar_api(_MonitoreoFalso(), puerto=PUERTO)

limite = time.time() + 5
while time.time() < limite:
    try:
        requests.get(f"{BASE}/docs", timeout=0.5)
        break
    except requests.exceptions.ConnectionError:
        time.sleep(0.1)

# 1) sin token no deja pasar
r = requests.get(f"{BASE}/camaras", timeout=3)
assert r.status_code == 401, r.text

# 2) login con la cuenta demo
r = requests.post(f"{BASE}/login", json={"usuario": "admin", "clave": "123456"}, timeout=5)
assert r.status_code == 200, r.text
token = r.json()["token"]
assert r.json()["rol"]
cabecera = {"Authorization": f"Bearer {token}"}

# 3) camaras (estado en vivo, viene del MonitoreoController falso)
r = requests.get(f"{BASE}/camaras", headers=cabecera, timeout=3)
assert r.status_code == 200, r.text
camaras = r.json()
assert camaras and camaras[0]["zona"] == "Cam-Ingreso-01" and camaras[0]["en_linea"] is True, camaras

# 4) incidencias (de verdad, de la base)
r = requests.get(f"{BASE}/incidencias?limite=5", headers=cabecera, timeout=5)
assert r.status_code == 200, r.text
assert isinstance(r.json(), list)

# 5) resumen
r = requests.get(f"{BASE}/resumen", headers=cabecera, timeout=5)
assert r.status_code == 200, r.text
resumen = r.json()
assert resumen["camaras_en_linea"] == 1 and resumen["camaras_total"] == 3, resumen

# 6) stream en vivo de una camara (multipart MJPEG)
r = requests.get(f"{BASE}/camaras/Cam-Ingreso-01/stream.mjpg", headers=cabecera, stream=True, timeout=5)
assert r.status_code == 200, r.text
assert r.headers["content-type"].startswith("multipart/x-mixed-replace")
primer_cuadro = next(r.iter_content(chunk_size=4096))
assert b"\xff\xd8" in primer_cuadro
r.close()

# 7) stream de una camara que no existe
r = requests.get(f"{BASE}/camaras/Zona-Que-No-Existe/stream.mjpg", headers=cabecera, timeout=3)
assert r.status_code == 404, r.text

# 8) login con clave mala
r = requests.post(f"{BASE}/login", json={"usuario": "admin", "clave": "no-es-esta"}, timeout=5)
assert r.status_code == 401, r.text

print("OK: API (login, camaras, incidencias, resumen) funciona de punta a punta")
os._exit(0)
