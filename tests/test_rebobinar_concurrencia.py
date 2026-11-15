import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
from app.services.camera_service import CamaraThread

# el hilo de captura agrega cuadros al buffer mientras el telefono pide el
# rebobinado: obtener_buffer_jpeg_brillante no debe romper con
# "deque mutated during iteration"
hilo = CamaraThread(1, "w", "w", "USB", "0")
jpg = cv2.imencode(".jpg", np.full((10, 10, 3), 40, np.uint8))[1].tobytes()
for _ in range(20):
    hilo._buffer.append(jpg)

parar = threading.Event()

def capturar():
    while not parar.is_set():
        hilo._buffer.append(jpg)
        time.sleep(0.0005)

t = threading.Thread(target=capturar, daemon=True)
t.start()
fin = time.time() + 1.5
llamadas = 0
try:
    while time.time() < fin:
        hilo.obtener_buffer_jpeg_brillante()
        llamadas += 1
finally:
    parar.set()
    t.join()
print(f"OK: rebobinado sin crash con buffer en vivo ({llamadas} llamadas)")
