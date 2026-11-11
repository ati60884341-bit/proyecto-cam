"""Sirena sonora fuerte para alertas de sabotaje (camara tapada/movida).

Antes solo sonaba QApplication.beep(): el "ding" suave de Windows, facil de
no oir en una garita. Aqui se genera una sirena de dos tonos a volumen
maximo (WAV, sin dependencias nuevas: numpy ya esta en el proyecto) y se
reproduce en bucle con winsound hasta que se destape la camara, el
vigilante la silencie, o pase el tiempo maximo.
"""
import math
import os
import struct
import tempfile
import wave

try:
    import winsound
except ImportError:  # no-Windows: sin sirena, se cae al beep de Qt
    winsound = None

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


def iniciar_sirena():
    """Empieza la sirena en bucle (no bloquea). Devuelve False si no se pudo
    (ej. no es Windows): el que llama puede caer a un beep normal."""
    if winsound is None:
        return False
    try:
        winsound.PlaySound(
            _ruta_wav(),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP | winsound.SND_NODEFAULT,
        )
        return True
    except Exception:
        return False


def detener_sirena():
    if winsound is None:
        return
    try:
        winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:
        pass
