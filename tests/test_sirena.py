"""Correr con:  python tests/test_sirena.py   (suena en silencio: volumen 0)"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QCoreApplication

from app.services import alarma_service

app = QCoreApplication([])
alarma_service.preparar()
alarma_service._efecto.setVolume(0.0)
fin = time.time() + 3
while time.time() < fin:
    app.processEvents()
    time.sleep(0.01)

for _ in range(3):
    inicio = time.perf_counter()
    assert alarma_service.iniciar_sirena(), "la sirena no arranco"
    arranque_ms = (time.perf_counter() - inicio) * 1000
    time.sleep(0.15)
    app.processEvents()
    inicio = time.perf_counter()
    alarma_service.detener_sirena()
    parada_ms = (time.perf_counter() - inicio) * 1000
    # con winsound apagar la sirena congelaba la ventana 5-10 s
    assert arranque_ms < 100 and parada_ms < 100, (arranque_ms, parada_ms)

print("OK sirena: arranca y se apaga sin trabar")
