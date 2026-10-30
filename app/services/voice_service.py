import re

from PyQt6.QtCore import QThread, pyqtSignal

ZONAS_VALIDAS = ["ingreso", "patio", "estacionamiento", "pasillo"]


def registrar_zona(nombre):
    """Permite que comandos de voz reconozcan zonas agregadas en caliente
    (al dar de alta una camara nueva de cualquier marca)."""
    clave = nombre.lower().strip()
    if clave and clave not in ZONAS_VALIDAS:
        ZONAS_VALIDAS.append(clave)


DIRECCIONES_PTZ = {
    "izquierda": "izquierda", "a la izquierda": "izquierda",
    "derecha": "derecha", "a la derecha": "derecha",
    "arriba": "arriba", "hacia arriba": "arriba",
    "abajo": "abajo", "hacia abajo": "abajo",
}


def interpretar_comando(texto):
    """Interpreta un comando en texto libre y devuelve (accion, zona, texto_original).
    accion es uno de: 'ampliar', 'capturar', 'zoom_in', 'zoom_out', 'zoom_reset',
    'mover_izquierda'/'mover_derecha'/'mover_arriba'/'mover_abajo' (PTZ real,
    ej. Tapo C510W), 'vista_general', 'desconocido'."""
    texto_normalizado = texto.lower().strip()

    zona_encontrada = next((z for z in ZONAS_VALIDAS if z in texto_normalizado), None)

    if "vista general" in texto_normalizado or "mostrar todo" in texto_normalizado:
        return "vista_general", None, texto

    if re.search(r"mover|gira|girar|voltear|rota|rotar|apunta|apuntar", texto_normalizado):
        direccion = next((d for clave, d in DIRECCIONES_PTZ.items() if clave in texto_normalizado), None)
        if direccion:
            return f"mover_{direccion}", zona_encontrada, texto

    if re.search(r"zoom normal|quitar zoom|restablecer zoom|zoom original|sin zoom", texto_normalizado):
        return "zoom_reset", zona_encontrada, texto

    if re.search(r"alejar|aleja|zoom out|reducir zoom|alejate", texto_normalizado):
        return "zoom_out", zona_encontrada, texto

    if re.search(r"acercar|acerca|zoom in|amplificar|haz zoom|hacer zoom|\bzoom\b", texto_normalizado):
        return "zoom_in", zona_encontrada, texto

    if re.search(r"ampliar|pantalla completa|mostrar", texto_normalizado) and zona_encontrada:
        return "ampliar", zona_encontrada, texto

    if re.search(r"captur|evidencia|foto", texto_normalizado):
        return "capturar", zona_encontrada, texto

    return "desconocido", zona_encontrada, texto


class AsistenteVozThread(QThread):
    """Escucha el microfono en un hilo aparte para no congelar la UI (QThread)."""

    comando_reconocido = pyqtSignal(str, object, str)  # accion, zona, texto_original
    error_reconocimiento = pyqtSignal(str)
    escuchando = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._activo = True

    def detener(self):
        self._activo = False

    def run(self):
        try:
            import speech_recognition as sr
        except ImportError:
            self.error_reconocimiento.emit("El modulo SpeechRecognition no esta instalado.")
            return

        reconocedor = sr.Recognizer()
        try:
            microfono = sr.Microphone()
        except Exception as exc:
            self.error_reconocimiento.emit(f"No se encontro microfono disponible: {exc}")
            return

        with microfono as fuente:
            reconocedor.adjust_for_ambient_noise(fuente, duration=1)

        while self._activo:
            try:
                self.escuchando.emit(True)
                with microfono as fuente:
                    audio = reconocedor.listen(fuente, timeout=5, phrase_time_limit=6)
                self.escuchando.emit(False)

                texto = reconocedor.recognize_google(audio, language="es-ES")
                accion, zona, _ = interpretar_comando(texto)
                self.comando_reconocido.emit(accion, zona, texto)
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except Exception as exc:
                self.escuchando.emit(False)
                self.error_reconocimiento.emit(str(exc))
                self.msleep(1500)


def hablar(texto):
    """Sintesis de voz (TTS) de respuesta. Falla en silencio si no hay motor disponible."""
    try:
        import pyttsx3

        motor = pyttsx3.init()
        motor.setProperty("rate", 175)
        motor.say(texto)
        motor.runAndWait()
        motor.stop()
    except Exception:
        pass
