"""Correr con:  python tests/test_optimizacion_inicio.py

Antes, dos consultas a la base de datos se hacian en el hilo de la UI:
identificar el modelo de cada DVR/NVR al iniciar sesion, y contar las
incidencias de hoy cada 5 s mientras se ve la pantalla de Inicio. Con una
base lenta (red, VPN, SQL Server remoto) eso trababa la ventana. Este test
simula una base lenta y confirma que ya no frena al hilo que llama."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from app.controllers.monitoreo_controller import _ConsultaDispositivosThread
from app.controllers.inicio_controller import _ConsultaIncidenciasThread
from app.models import dispositivo_dvr_model, incidencia_model
from app.views.inicio_view import InicioView

aplicacion = QApplication.instance() or QApplication(sys.argv)

DEMORA_SIMULADA_SEG = 0.3
LIMITE_DEMORA_LLAMADOR_MS = 50


def _esperar(resultado, segundos=5):
    limite = time.time() + segundos
    while not resultado and time.time() < limite:
        aplicacion.processEvents()
        time.sleep(0.02)


# 1) identificar grabadores: una consulta lenta a la base no debe frenar al llamador
def _obtener_varios_lento(ids):
    time.sleep(DEMORA_SIMULADA_SEG)
    return [{"IdDispositivo": i, "Marca": "Dahua", "IP": "0.0.0.0"} for i in ids]


original_obtener_varios = dispositivo_dvr_model.obtener_varios
dispositivo_dvr_model.obtener_varios = _obtener_varios_lento
try:
    resultado = []
    hilo = _ConsultaDispositivosThread({1, 2})
    hilo.listos.connect(resultado.append)
    inicio = time.perf_counter()
    hilo.start()
    demora_ms = (time.perf_counter() - inicio) * 1000
    assert demora_ms < LIMITE_DEMORA_LLAMADOR_MS, f"_ConsultaDispositivosThread.start() freno al llamador {demora_ms:.0f} ms"
    _esperar(resultado)
finally:
    dispositivo_dvr_model.obtener_varios = original_obtener_varios
assert resultado and len(resultado[0]) == 2, f"no llegaron los 2 dispositivos: {resultado}"
print("OK: identificar grabadores no bloquea el hilo de la UI")


# 2) contar incidencias de Inicio: igual, una base lenta no debe frenar al llamador
def _contar_hoy_lento():
    time.sleep(DEMORA_SIMULADA_SEG)
    return 3


original_contar = incidencia_model.contar_hoy
incidencia_model.contar_hoy = _contar_hoy_lento
try:
    resultado2 = []
    hilo2 = _ConsultaIncidenciasThread()
    hilo2.listo.connect(resultado2.append)
    inicio = time.perf_counter()
    hilo2.start()
    demora_ms = (time.perf_counter() - inicio) * 1000
    assert demora_ms < LIMITE_DEMORA_LLAMADOR_MS, f"_ConsultaIncidenciasThread.start() freno al llamador {demora_ms:.0f} ms"
    _esperar(resultado2)
finally:
    incidencia_model.contar_hoy = original_contar
assert resultado2 == [3], f"no llego el conteo de incidencias: {resultado2}"
print("OK: conteo de incidencias de Inicio no bloquea el hilo de la UI")


# 3) la tarjeta de alertas al celular ya no existe en Inicio (set_resumen: 3 argumentos)
vista = InicioView({"NombreCompleto": "Prueba", "Rol": "Vigilante"})
assert not hasattr(vista, "tarjeta_alertas"), "la tarjeta de alertas deberia haberse quitado de Inicio"
vista.set_resumen(1, 9, 0)  # no debe pedir tipo/texto de alertas
print("OK: Inicio ya no muestra la tarjeta de alertas al celular")
