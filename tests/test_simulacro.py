"""Correr con:  python tests/test_simulacro.py

CamaraThread.disparar_simulacro() reutiliza el pipeline de exportacion de
evidencia de sabotaje para un disparo manual de demo, en un hilo de fondo
real (igual que la deteccion real de sabotaje). La senal sabotaje_detectado
gana un 4to parametro es_simulacro para distinguir ambos casos."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
from PySide6.QtWidgets import QApplication
from app.services.camera_service import CamaraThread

aplicacion = QApplication.instance() or QApplication([])
hilo = CamaraThread(1, "zona1", "zona1", "USB", "0")
jpg = cv2.imencode(".jpg", np.zeros((10, 10, 3), np.uint8))[1]  # ndarray, igual que el buffer real (linea ~566)
hilo._buffer.append(jpg)
hilo._ultimo_frame = np.zeros((10, 10, 3), np.uint8)

resultado = []
hilo.sabotaje_detectado.connect(lambda *args: resultado.append(args))
hilo.disparar_simulacro()

limite = time.time() + 5
while not resultado and time.time() < limite:
    aplicacion.processEvents()
    time.sleep(0.02)

assert resultado, "no llego la señal sabotaje_detectado"
zona, ruta_video, ruta_foto, es_simulacro = resultado[0]
assert zona == "zona1" and es_simulacro is True
print("OK: disparar_simulacro")

# --- Tarea 12: _on_sabotaje(es_simulacro=True) debe registrar Tipo="Simulacro" ---
from unittest.mock import MagicMock
from app.controllers.monitoreo_controller import MonitoreoController
from app.models import incidencia_model

capturado_t12 = {}


def _crear_incidencia_stub_t12(id_zona, tipo, descripcion, **kwargs):
    capturado_t12["tipo"] = tipo
    capturado_t12["severidad"] = kwargs.get("severidad")
    return 1


# se evita el __init__ real (arranca sirena/QSoundEffect, hilos de camara,
# AuditorFatiga, etc. - innecesario y deja cosas vivas que traban la salida
# del proceso); solo necesitamos lo que _on_sabotaje de verdad usa
controller = MonitoreoController.__new__(MonitoreoController)
controller.view = MagicMock()
controller.usuario = {"IdUsuario": 1}
controller.obtener_turno_actual = lambda: 1
controller.camaras_por_zona = {"zona1": {"IdZona": 1, "IdCamara": 1}}

original_crear_t12 = incidencia_model.crear
incidencia_model.crear = _crear_incidencia_stub_t12
try:
    controller._on_sabotaje("zona1", "video.avi", "foto.jpg", True)
    limite = time.time() + 5
    while "tipo" not in capturado_t12 and time.time() < limite:
        aplicacion.processEvents()
        time.sleep(0.02)
finally:
    incidencia_model.crear = original_crear_t12

assert capturado_t12.get("tipo") == "Simulacro", capturado_t12
assert capturado_t12.get("severidad") == "Normal", capturado_t12
print("OK: _on_sabotaje con es_simulacro=True registra Tipo=Simulacro")

# --- Tarea 12: MonitoreoController.disparar_simulacro(zona) ---
from app.services import alarma_service


class _HiloFalsoT12:
    def __init__(self):
        self.simulacros_disparados = 0

    def disparar_simulacro(self):
        self.simulacros_disparados += 1


class _TimerFalsoT12:
    def start(self, ms):
        pass


hilo_falso_t12 = _HiloFalsoT12()
# igual que en __init__ (que este test se saltea): el puente se crea en el
# hilo de la UI
from app.controllers.monitoreo_controller import _PuenteSimulacro
controller._puente_simulacro = _PuenteSimulacro()
controller._puente_simulacro.disparado.connect(controller._activar_alarma)
controller.hilos_camara = {"zona1": hilo_falso_t12}
controller._alarma_sonando = False
controller._timer_alarma = _TimerFalsoT12()
controller._zonas_en_sabotaje = set()
controller.view.set_alarma_sonando.reset_mock()

original_iniciar_sirena_t12 = alarma_service.iniciar_sirena
alarma_service.iniciar_sirena = lambda: True
try:
    # zona desconocida: False, sin tocar la alarma
    assert controller.disparar_simulacro("Zona-Que-No-Existe") is False
    assert controller._alarma_sonando is False
    controller.view.set_alarma_sonando.assert_not_called()
    assert hilo_falso_t12.simulacros_disparados == 0

    # zona conocida: True, dispara el hilo y prende la alarma
    assert controller.disparar_simulacro("zona1") is True
    assert hilo_falso_t12.simulacros_disparados == 1
    assert controller._alarma_sonando is True
    controller.view.set_alarma_sonando.assert_called_once_with(True, [])
    assert controller._zonas_en_sabotaje == set()
finally:
    alarma_service.iniciar_sirena = original_iniciar_sirena_t12

print("OK: MonitoreoController.disparar_simulacro")

# --- revision final: desde otro hilo (como uvicorn) la alarma corre en el hilo de la UI ---
import threading

hilos_alarma = []
controller._alarma_sonando = False
puente2 = _PuenteSimulacro()
puente2.disparado.connect(lambda: hilos_alarma.append(threading.current_thread()))
controller._puente_simulacro = puente2
t = threading.Thread(target=controller.disparar_simulacro, args=("zona1",))
t.start()
t.join()
limite = time.time() + 3
while not hilos_alarma and time.time() < limite:
    aplicacion.processEvents()
    time.sleep(0.02)
assert hilos_alarma, "la senal del simulacro nunca llego al hilo de la UI"
assert hilos_alarma[0] is threading.main_thread(), hilos_alarma[0]
print("OK: disparar_simulacro desde otro hilo salta al hilo de la UI")

# --- revision final: la alerta al celular de un simulacro dice que es simulacro ---
from app.services import alertas_service

textos = []
original_enviar = alertas_service.enviar_alerta_async
alertas_service.enviar_alerta_async = lambda ruta, texto, **k: textos.append(texto)
controller._puente_alertas = MagicMock()
try:
    controller._evidencia_sabotaje_lista("zona1", "[SIMULACRO] x", ("foto.jpg", "abc"), True)
    controller._evidencia_sabotaje_lista("zona1", "[EVIDENCIA] x", ("foto.jpg", "abc"), False)
finally:
    alertas_service.enviar_alerta_async = original_enviar
assert textos[0].startswith("🧪 SIMULACRO (no es un sabotaje real)"), textos[0]
assert textos[1].startswith("🚨 ALERTA: camara tapada o movida"), textos[1]
print("OK: alerta de simulacro rotulada, la real sin cambios")

os._exit(0)
