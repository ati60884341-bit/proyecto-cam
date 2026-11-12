import re
import threading
import time
import unicodedata

from PyQt6.QtCore import QThread, pyqtSignal

NUMEROS = {
    "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
    "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
}
# palabras que aparecen en muchos nombres de camara y no sirven para distinguir una
PALABRAS_COMUNES = {"cam", "camara", "canal", "dvr", "nvr", "prueba", "simulacion", "zona", "de", "la", "el", "del"}


def normalizar(texto):
    """minusculas y sin tildes: el reconocimiento de voz no siempre acierta
    los acentos (y los nombres que el instalador escribe pueden tenerlos)."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sin_tildes.lower().strip()


def _plano(texto):
    """'DVR-Patio-Canal3' y lo dicho "dvr patio canal tres" quedan igual:
    ' dvr patio canal 3 ' (con espacios en los bordes para buscar palabras)."""
    t = normalizar(texto)
    t = re.sub(r"([a-z])(\d)", r"\1 \2", t)
    t = re.sub(r"(\d)([a-z])", r"\1 \2", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    palabras = [str(NUMEROS.get(p, p)) for p in t.split()]
    return f" {' '.join(palabras)} "


def buscar_camara(texto, camaras):
    """camaras: lista de (numero, nombre) tal como se ven en el Centro de
    Monitoreo. Devuelve el nombre de la camara nombrada en `texto`, o None.

    1) "camara 3" -> la que muestra el numero 3 (lo mas facil de decir).
    2) si no, gana la camara con mas palabras propias de su nombre dichas
       ("ingreso zoom" -> "Cam-Ingreso-01"); "canal N" descarta las de otro
       canal. Si dos empatan, no se adivina: None."""
    dicho = _plano(texto)
    numero = re.search(r" camara (?:numero |nro )?(\d+) ", dicho)
    if numero:
        n = int(numero.group(1))
        return next((nombre for num, nombre in camaras if num == n), None)

    canal = re.search(r" canal (\d+) ", dicho)
    puntajes = []
    for _, nombre in camaras:
        plano = _plano(nombre)
        canal_propio = re.search(r" canal (\d+) ", plano)
        if canal and canal_propio and canal_propio.group(1) != canal.group(1):
            continue
        propias = {p for p in plano.split() if p not in PALABRAS_COMUNES and not p.isdigit() and len(p) >= 3}
        puntaje = sum(1 for p in propias if f" {p} " in dicho)
        if canal and canal_propio:
            puntaje += 2
        if puntaje:
            puntajes.append((puntaje, nombre))
    if not puntajes:
        return None
    puntajes.sort(reverse=True)
    if len(puntajes) > 1 and puntajes[0][0] == puntajes[1][0]:
        return None
    return puntajes[0][1]


DIRECCIONES_PTZ = {
    "izquierda": "izquierda", "a la izquierda": "izquierda",
    "derecha": "derecha", "a la derecha": "derecha",
    "arriba": "arriba", "hacia arriba": "arriba",
    "abajo": "abajo", "hacia abajo": "abajo",
}


def interpretar_comando(texto, camaras=()):
    """Interpreta un comando en texto libre y devuelve
    (accion, camara, texto_original, numero_preset); camaras como en buscar_camara().
    accion es uno de: 'ampliar', 'capturar', 'zoom_in', 'zoom_out', 'zoom_reset',
    'mover_izquierda'/'mover_derecha'/'mover_arriba'/'mover_abajo' (PTZ real),
    'preset_guardar'/'preset_ir' (posiciones PTZ guardadas, con numero_preset),
    'vista_general', 'desconocido'. numero_preset es None salvo en los
    comandos de preset."""
    texto_normalizado = _plano(texto).strip()

    zona_encontrada = buscar_camara(texto, camaras)

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


class GrabacionVozThread(QThread):
    """"Mantener para hablar": graba TODO mientras el boton esta apretado y
    recien al soltarlo lo manda a reconocer. Antes se escuchaba con
    listen(), que corta la frase en la primera pausa: "ingreso ... zoom"
    llegaba como solo "ingreso"."""

    texto_reconocido = pyqtSignal(str)
    texto_parcial = pyqtSignal(str)       # lo entendido hasta ahora, mientras se habla
    error_reconocimiento = pyqtSignal(str)

    COLA_SEG = 0.3        # se sigue grabando un poco tras soltar: la ultima palabra no se corta
    MINIMO_SEG = 0.4
    CADA_PARCIAL_SEG = 1.0

    def __init__(self, device_index=None, parent=None):
        super().__init__(parent)
        self.device_index = device_index
        self._grabando = True
        self._parcial_ocupado = False

    def soltar(self):
        self._grabando = False

    def _reconocer_parcial(self, sr, datos, frecuencia, ancho):
        """En un hilo aparte (no frena la grabacion): manda lo grabado hasta
        ahora y muestra lo que se va entendiendo."""
        try:
            texto = sr.Recognizer().recognize_google(sr.AudioData(datos, frecuencia, ancho), language="es-PE")
            if self._grabando:
                self.texto_parcial.emit(texto)
        except Exception:
            pass  # todavia no se entiende nada: se reintenta en el proximo turno
        finally:
            self._parcial_ocupado = False

    def run(self):
        try:
            import speech_recognition as sr
        except ImportError:
            self.error_reconocimiento.emit("Falta el modulo SpeechRecognition.")
            return
        try:
            with sr.Microphone(device_index=self.device_index) as fuente:
                trozos = []
                ultimo_parcial = time.time()
                while self._grabando:
                    trozos.append(fuente.stream.read(fuente.CHUNK))
                    if not self._parcial_ocupado and time.time() - ultimo_parcial >= self.CADA_PARCIAL_SEG:
                        ultimo_parcial = time.time()
                        self._parcial_ocupado = True
                        threading.Thread(
                            target=self._reconocer_parcial,
                            args=(sr, b"".join(trozos), fuente.SAMPLE_RATE, fuente.SAMPLE_WIDTH),
                            daemon=True,
                        ).start()
                for _ in range(int(self.COLA_SEG * fuente.SAMPLE_RATE / fuente.CHUNK)):
                    trozos.append(fuente.stream.read(fuente.CHUNK))
                frecuencia, ancho = fuente.SAMPLE_RATE, fuente.SAMPLE_WIDTH
        except Exception as exc:
            self.error_reconocimiento.emit(f"No se pudo usar el microfono: {exc}")
            return

        datos = b"".join(trozos)
        if len(datos) < self.MINIMO_SEG * frecuencia * ancho:
            self.error_reconocimiento.emit("Muy corto: mantenga apretado mientras habla.")
            return
        try:
            texto = sr.Recognizer().recognize_google(sr.AudioData(datos, frecuencia, ancho), language="es-PE")
        except sr.UnknownValueError:
            self.error_reconocimiento.emit("No se entendio. Hable mas cerca del microfono.")
            return
        except Exception as exc:
            self.error_reconocimiento.emit(f"Sin servicio de reconocimiento (¿internet?): {exc}")
            return
        self.texto_reconocido.emit(texto)


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
