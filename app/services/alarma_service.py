"""Sirena sonora fuerte para alertas de sabotaje (camara tapada/movida).

Antes solo sonaba QApplication.beep(): el "ding" suave de Windows, facil de
no oir en una garita. Aqui se genera una sirena de dos tonos a volumen
maximo (WAV) y se reproduce en bucle con QSoundEffect (Qt) hasta que se
destape la camara, el vigilante la silencie, o pase el tiempo maximo.

No con winsound: apagar un sonido en bucle de winsound bloqueaba 5-10 s
(medido), y como se apaga desde la interfaz, el programa entero se
congelaba justo al destapar la camara. Se usa siempre desde el hilo de la UI.
"""
import math
import os
import struct
import tempfile
import wave

FRECUENCIA_MUESTREO = 22050
_ruta_sirena = None


def _generar_sirena(ruta, segundos=2.0):
    """Sirena tipo "wail" de policia: barrido 650 Hz <-> 1500 Hz, onda casi
    cuadrada (mas armonicos = se percibe mucho mas fuerte que una senoidal
    al mismo volumen) y amplitud al 95% del maximo de 16 bits."""
    n = int(FRECUENCIA_MUESTREO * segundos)
    fase = 0.0
    muestras = bytearray()
    for i in range(n):
        t = i / FRECUENCIA_MUESTREO
        # sube y baja una vez por cada 1 s
        barrido = 0.5 - 0.5 * math.cos(2 * math.pi * t / 1.0)
        freq = 650 + (1500 - 650) * barrido
        fase += 2 * math.pi * freq / FRECUENCIA_MUESTREO
        s = math.sin(fase)
        # "satura" la senoidal hacia cuadrada
        valor = math.tanh(4.0 * s) / math.tanh(4.0)
        muestras += struct.pack("<h", int(valor * 0.95 * 32767))
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FRECUENCIA_MUESTREO)
        w.writeframes(bytes(muestras))


def _ruta_wav():
    global _ruta_sirena
    if _ruta_sirena and os.path.exists(_ruta_sirena):
        return _ruta_sirena
    ruta = os.path.join(tempfile.gettempdir(), "cam_sirena_sabotaje.wav")
    if not os.path.exists(ruta):
        _generar_sirena(ruta)
    _ruta_sirena = ruta
    return ruta


_efecto = None


def preparar():
    """Carga la sirena por adelantado (se carga en segundo plano): asi la
    primera alarma suena al instante. Requiere la QApplication creada."""
    global _efecto
    if _efecto is not None:
        return
    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QSoundEffect
    except ImportError:
        return
    _efecto = QSoundEffect()
    _efecto.setSource(QUrl.fromLocalFile(_ruta_wav()))
    _efecto.setLoopCount(QSoundEffect.Loop.Infinite.value)
    _efecto.setVolume(1.0)


def iniciar_sirena():
    """Empieza la sirena en bucle (no bloquea). Devuelve False si no se pudo:
    el que llama puede caer a un beep normal."""
    preparar()
    if _efecto is None:
        return False
    _efecto.play()
    return True


def detener_sirena():
    if _efecto is not None:
        _efecto.stop()
