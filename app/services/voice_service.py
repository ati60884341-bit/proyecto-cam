import re
import unicodedata

from PyQt6.QtCore import QThread, pyqtSignal

ZONAS_VALIDAS = ["ingreso", "patio", "estacionamiento", "pasillo"]


def normalizar(texto):
    """minusculas y sin tildes: el reconocimiento de voz no siempre acierta
    los acentos (y las zonas que el instalador escribe a mano en "Camaras"
    pueden tener tildes), asi que todo se compara sin ellos."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sin_tildes.lower().strip()


def registrar_zona(nombre):
    """Permite que comandos de voz reconozcan zonas agregadas en caliente
    (al dar de alta una camara nueva de cualquier marca, o un canal de la
    pestana "NVR / DVR"). Se guarda el nombre normalizado (sin tildes):
    la comparacion en interpretar_comando() tambien normaliza lo dicho,
    asi que siempre terminan coincidiendo igual."""
    clave = normalizar(nombre)
    if clave and clave not in ZONAS_VALIDAS:
        ZONAS_VALIDAS.append(clave)


def _buscar_zona(texto_normalizado):
    """Coincidencia directa primero (el nombre de la zona aparece en lo
    dicho); si hay varias zonas cuyo nombre aparece en lo dicho, gana la
    MAS LARGA (mas especifica) - sin esto, una zona de un canal DVR como
    "DVR Patio Central Canal 1" siempre perdia contra la zona corta
    "Patio" (que es literalmente una subcadena suya). Si no hay ninguna,
    prueba el atajo "canal N": las zonas que crea la pestana "NVR / DVR"
    se llaman "<Nombre del grabador> Canal N", y decir el nombre completo
    del grabador por voz es poco practico - con decir "canal 3" alcanza
    si hay una sola zona que termine asi."""
    candidatas = [z for z in ZONAS_VALIDAS if z in texto_normalizado]
    if candidatas:
        return max(candidatas, key=len)

    canal = re.search(r"canal\s*(\d+)", texto_normalizado)
    if canal:
        sufijo = f"canal {canal.group(1)}"
        candidatas = [z for z in ZONAS_VALIDAS if z.endswith(sufijo)]
        if len(candidatas) == 1:
            return candidatas[0]
    return None


DIRECCIONES_PTZ = {
    "izquierda": "izquierda", "a la izquierda": "izquierda",
    "derecha": "derecha", "a la derecha": "derecha",
    "arriba": "arriba", "hacia arriba": "arriba",
    "abajo": "abajo", "hacia abajo": "abajo",
}


def interpretar_comando(texto):
    """Interpreta un comando en texto libre y devuelve
    (accion, zona, texto_original, numero_preset).
    accion es uno de: 'ampliar', 'capturar', 'zoom_in', 'zoom_out', 'zoom_reset',
    'mover_izquierda'/'mover_derecha'/'mover_arriba'/'mover_abajo' (PTZ real),
    'preset_guardar'/'preset_ir' (posiciones PTZ guardadas, con numero_preset),
    'vista_general', 'desconocido'. numero_preset es None salvo en los
    comandos de preset."""
    texto_normalizado = normalizar(texto)

    zona_encontrada = _buscar_zona(texto_normalizado)

    if "vista general" in texto_normalizado or "mostrar todo" in texto_normalizado:
        return "vista_general", None, texto, None

    preset = re.search(r"preset\s*(\d+)", texto_normalizado)
    if preset:
        numero_preset = int(preset.group(1))
        if re.search(r"guarda|grabar|memoriza|fija", texto_normalizado):
            return "preset_guardar", zona_encontrada, texto, numero_preset
        return "preset_ir", zona_encontrada, texto, numero_preset

    if re.search(r"mover|gira|girar|voltear|rota|rotar|apunta|apuntar", texto_normalizado):
        direccion = next((d for clave, d in DIRECCIONES_PTZ.items() if clave in texto_normalizado), None)
        if direccion:
            return f"mover_{direccion}", zona_encontrada, texto, None

    if re.search(r"zoom normal|quitar zoom|restablecer zoom|zoom original|sin zoom", texto_normalizado):
        return "zoom_reset", zona_encontrada, texto, None

    if re.search(r"alejar|aleja|zoom out|reducir zoom|alejate", texto_normalizado):
        return "zoom_out", zona_encontrada, texto, None

    if re.search(r"acercar|acerca|zoom in|amplificar|haz zoom|hacer zoom|\bzoom\b", texto_normalizado):
        return "zoom_in", zona_encontrada, texto, None

    if re.search(r"ampliar|pantalla completa|mostrar", texto_normalizado) and zona_encontrada:
        return "ampliar", zona_encontrada, texto, None

    if re.search(r"captur|evidencia|foto", texto_normalizado):
        return "capturar", zona_encontrada, texto, None

    return "desconocido", zona_encontrada, texto, None


def listar_microfonos():
    """Lista (indice, nombre) de los microfonos reales que Windows tiene
    detectados, para elegir el real en vez del "predeterminado" (que puede
    seguir apuntando a un Bluetooth ya desconectado).

    sr.Microphone.list_microphone_names() (lo que se usaba antes) devuelve
    TODOS los dispositivos de audio que ve PyAudio, mezclando entradas y
    salidas y repitiendo cada uno una vez por cada API de sonido vieja de
    Windows (MME, DirectSound, WASAPI, WDM-KS) - en una PC normal eso son
    30-40 "microfonos" en el desplegable, inentendible para alguien que
    solo quiere elegir el suyo. Aqui se usa PyAudio directo, filtrando a
    WASAPI (la API moderna: nombres completos, sin duplicar entre APIs) y
    solo dispositivos de ENTRADA de verdad."""
    try:
        import pyaudio
    except ImportError:
        return []
    try:
        audio = pyaudio.PyAudio()
    except Exception:
        return []
    try:
        indice_api = None
        for h in range(audio.get_host_api_count()):
            info_api = audio.get_host_api_info_by_index(h)
            if "WASAPI" in info_api["name"]:
                indice_api = info_api["index"]
                break
        if indice_api is None:
            indice_api = audio.get_default_host_api_info()["index"]

        dispositivos = []
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if info.get("hostApi") != indice_api:
                continue
            if info.get("maxInputChannels", 0) <= 0:
                continue
            nombre = info["name"].strip()
            if "sound mapper" in nombre.lower():
                continue  # eso ya es la opcion "Microfono por defecto de Windows"
            dispositivos.append((i, nombre))
        return dispositivos
    except Exception:
        return []
    finally:
        audio.terminate()


class AsistenteVozThread(QThread):
    """Escucha el microfono en un hilo aparte para no congelar la UI (QThread)."""

    comando_reconocido = pyqtSignal(str, object, str, object)  # accion, zona, texto_original, numero_preset
    error_reconocimiento = pyqtSignal(str)
    escuchando = pyqtSignal(bool)

    def __init__(self, device_index=None, parent=None):
        super().__init__(parent)
        self._activo = True
        self.device_index = device_index

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
            microfono = sr.Microphone(device_index=self.device_index)
        except Exception as exc:
            self.error_reconocimiento.emit(f"No se encontro microfono disponible: {exc}")
            return

        try:
            with microfono as fuente:
                reconocedor.adjust_for_ambient_noise(fuente, duration=1)
        except Exception as exc:
            # sin este try/except, un fallo aqui (ej. el dispositivo elegido
            # ya no existe, o quedo ocupado por otra app) mataba el hilo en
            # silencio: el checkbox quedaba marcado pero nunca emitia
            # "escuchando" ni ningun error, y el usuario no entendia por que
            self.error_reconocimiento.emit(f"No se pudo preparar el microfono: {exc}")
            return

        while self._activo:
            try:
                self.escuchando.emit(True)
                with microfono as fuente:
                    audio = reconocedor.listen(fuente, timeout=5, phrase_time_limit=6)
                self.escuchando.emit(False)

                texto = reconocedor.recognize_google(audio, language="es-PE")
                accion, zona, _, numero_preset = interpretar_comando(texto)
                self.comando_reconocido.emit(accion, zona, texto, numero_preset)
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
