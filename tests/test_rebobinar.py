import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
from app.services.camera_service import CamaraThread

hilo = CamaraThread(1, "w", "w", "USB", "0")
assert hilo.obtener_buffer_jpeg_brillante() == [], "sin buffer todavia, debe dar lista vacia"

oscuro = cv2.imencode(".jpg", np.full((10, 10, 3), 40, np.uint8))[1].tobytes()
hilo._buffer.append(oscuro)
hilo._buffer.append(oscuro)
cuadros = hilo.obtener_buffer_jpeg_brillante()
assert len(cuadros) == 2
decodificado = cv2.imdecode(np.frombuffer(cuadros[0], np.uint8), cv2.IMREAD_COLOR)
assert decodificado.mean() > 40 + 10, "debe salir mas claro, igual que obtener_ultimo_jpeg"
print("OK: obtener_buffer_jpeg_brillante")
