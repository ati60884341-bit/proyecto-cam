"""Correr con:  python tests/test_camara_jpeg.py   (no usa la camara)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import cv2

from app.services.camera_service import CamaraThread

hilo = CamaraThread(1, "w", "w", "USB", "0")
assert hilo.obtener_ultimo_jpeg() is None, "sin frame todavia, debe dar None"

hilo._ultimo_frame = np.zeros((480, 640, 3), np.uint8)
jpg = hilo.obtener_ultimo_jpeg()
assert isinstance(jpg, bytes) and jpg[:2] == b"\xff\xd8", "debe ser un JPEG valido"
decodificado = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
assert decodificado.shape == (480, 640, 3)
print("OK: obtener_ultimo_jpeg")
