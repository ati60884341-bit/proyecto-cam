import os
import socket
import threading
import time
from collections import deque
from urllib.parse import urlparse

# el backend FFMPEG de OpenCV solo respeta el timeout de conexion RTSP via
# esta variable de entorno (CAP_PROP_OPEN_TIMEOUT_MSEC no siempre funciona);
# debe fijarse antes de abrir cualquier VideoCapture RTSP
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;4000000|timeout;4000000|max_delay;500000",
)

import cv2
from PyQt6.QtCore import QThread, pyqtSignal

from app.config import BUFFER_SEGUNDOS, CAPTURA_FPS, UMBRAL_SABOTAJE, EVIDENCIAS_DIR

TIMEOUT_CONEXION_RTSP_SEG = 4.0
LECTURAS_FALLIDAS_PARA_RECONECTAR = 40  # ~2s de lecturas fallidas seguidas -> reconectar
RESINCRONIZACION_PERIODICA_SEG = 120    # reconexion preventiva: limita cuanto se acumula
                                         # la corrupcion H.264 entre fotogramas clave (I-frames)


def _abrir_captura(tipo_conexion, url_conexion):
    if tipo_conexion == "USB":
        try:
            indice = int(url_conexion)
        except (TypeError, ValueError):
            indice = 0
        return cv2.VideoCapture(indice, cv2.CAP_DSHOW)

    cap = cv2.VideoCapture()
    try:
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 4000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 4000)
    except Exception:
        pass
    cap.open(url_conexion, cv2.CAP_FFMPEG)
    try:
        # buffer minimo: sin esto, OpenCV acumula frames viejos en cola y el
        # video en pantalla se va atrasando cada vez mas respecto al tiempo real
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    return cap


def _servidor_alcanzable(url_rtsp, timeout=2.0):
    """Verificacion TCP rapida antes de invocar a FFmpeg: si el host:puerto no
    responde en `timeout` segundos, no tiene sentido lanzar el intento de
    apertura RTSP (que de otro modo puede tardar ~30s en fallar)."""
    try:
        partes = urlparse(url_rtsp)
        host = partes.hostname
        if not host:
            return True  # url no estandar: se deja intentar con cv2 igual
        puerto = partes.port or 554
        with socket.create_connection((host, puerto), timeout=timeout):
            return True
    except OSError:
        return False


def _abrir_captura_sin_bloqueo(tipo_conexion, url_conexion):
    """Para RTSP: ni OPENCV_FFMPEG_CAPTURE_OPTIONS ni CAP_PROP_OPEN_TIMEOUT_MSEC
    son fiables en todos los builds de OpenCV (algunos ignoran el timeout y
    heredan el timeout TCP del SO, ~30s). Primero se hace una verificacion TCP
    rapida (2s) y, solo si el host responde, se abre en un hilo aparte con un
    watchdog de TIMEOUT_CONEXION_RTSP_SEG adicional (el hilo sigue intentando
    en segundo plano como daemon si se excede, sin bloquear la UI ni al hilo
    de la camara)."""
    if tipo_conexion == "USB":
        return _abrir_captura(tipo_conexion, url_conexion)

    if not _servidor_alcanzable(url_conexion):
        return None

    resultado = {}

    def intentar():
        resultado["cap"] = _abrir_captura(tipo_conexion, url_conexion)

    hilo = threading.Thread(target=intentar, daemon=True)
    hilo.start()
    hilo.join(TIMEOUT_CONEXION_RTSP_SEG)
    if hilo.is_alive():
        return None
    return resultado.get("cap")


class CamaraThread(QThread):
    """Hilo independiente por camara (QThread): captura, deteccion de sabotaje
    y buffer RAM de los ultimos BUFFER_SEGUNDOS ("maquina del tiempo")."""

    frame_listo = pyqtSignal(object)          # numpy array BGR, para pintar en la UI
    estado_cambiado = pyqtSignal(str)         # "conectada" | "sin_senal" | "sabotaje"
    sabotaje_detectado = pyqtSignal(str, str, str)  # zona, ruta_video, ruta_foto

    def __init__(self, id_camara, zona, nombre_camara, tipo_conexion, url_conexion, parent=None):
        super().__init__(parent)
        self.id_camara = id_camara
        self.zona = zona
        self.nombre_camara = nombre_camara
        self.tipo_conexion = tipo_conexion
        self.url_conexion = url_conexion
        self._activo = True

        self._buffer = deque(maxlen=BUFFER_SEGUNDOS * CAPTURA_FPS)
        self._baseline_brillo = None
        self._en_sabotaje = False
        self._ultimo_sabotaje = 0.0
        self._forzar_reconexion = False

    def detener(self):
        self._activo = False

    def forzar_reconexion(self):
        """Pide resincronizar con un fotograma clave nuevo (ej. justo despues
        de un movimiento PTZ, cuando el video suele verse mas distorsionado)."""
        self._forzar_reconexion = True

    def _actualizar_sabotaje(self, frame):
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brillo = float(gris.mean())
        desviacion = float(gris.std())

        if self._baseline_brillo is None:
            self._baseline_brillo = brillo
            return

        cambio_brusco = abs(brillo - self._baseline_brillo) > UMBRAL_SABOTAJE and desviacion < 28.0
        ahora = time.time()
        enfriamiento_activo = (ahora - self._ultimo_sabotaje) < 15.0

        if cambio_brusco and not self._en_sabotaje and not enfriamiento_activo:
            self._en_sabotaje = True
            self._ultimo_sabotaje = ahora
            self.estado_cambiado.emit("sabotaje")
            self._exportar_evidencia_sabotaje()
        elif not cambio_brusco:
            if self._en_sabotaje:
                self.estado_cambiado.emit("conectada")
            self._en_sabotaje = False
            # linea base lenta: se adapta a cambios normales de iluminacion
            self._baseline_brillo = 0.98 * self._baseline_brillo + 0.02 * brillo

    def _exportar_evidencia_sabotaje(self):
        frames = list(self._buffer)
        if not frames:
            return
        marca_tiempo = time.strftime("%Y%m%d_%H%M%S")
        base = f"sabotaje_{self.zona}_{marca_tiempo}".replace(" ", "_")

        # foto ~2 segundos antes del bloqueo (el rostro del culpable acercandose)
        indice_foto = max(0, len(frames) - 2 * CAPTURA_FPS)
        ruta_foto = os.path.join(EVIDENCIAS_DIR, base + ".jpg")
        cv2.imwrite(ruta_foto, frames[indice_foto])

        # video con los BUFFER_SEGUNDOS previos al bloqueo (la "maquina del tiempo")
        alto, ancho = frames[0].shape[:2]
        ruta_video = os.path.join(EVIDENCIAS_DIR, base + ".avi")
        escritor = cv2.VideoWriter(ruta_video, cv2.VideoWriter_fourcc(*"XVID"), CAPTURA_FPS, (ancho, alto))
        for f in frames:
            escritor.write(f)
        escritor.release()

        self.sabotaje_detectado.emit(self.zona, ruta_video, ruta_foto)

    def run(self):
        # bucle externo: (re)conecta; si la transmision se degrada de forma
        # sostenida, se reabre la captura entera en vez de quedarse mostrando
        # "sin senal" para siempre (se resincroniza con un fotograma clave
        # nuevo, lo que tambien ayuda con la fluidez tras un movimiento PTZ)
        while self._activo:
            captura = _abrir_captura_sin_bloqueo(self.tipo_conexion, self.url_conexion)
            if not captura or not captura.isOpened():
                self.estado_cambiado.emit("sin_senal")
                self.msleep(3000)
                continue

            self._forzar_reconexion = False  # descarta pedidos de reconexion viejos, ya se reconecto

            self.estado_cambiado.emit("conectada")
            if not self._transmitir(captura):
                self.estado_cambiado.emit("sin_senal")
            captura.release()

    def _transmitir(self, captura):
        """Lee y procesa frames hasta que se pida detener o la transmision se
        degrade de forma sostenida. Devuelve False cuando hay que reconectar."""
        intervalo = 1.0 / CAPTURA_FPS
        fallos_seguidos = 0
        ultimo_procesado = 0.0
        inicio_transmision = time.time()
        es_rtsp = self.tipo_conexion != "USB"

        while self._activo:
            # se lee SIN pausa, tan rapido como llegan los frames: en RTSP esto
            # drena la cola de red/decodificador y evita que el video se vaya
            # atrasando respecto al tiempo real (si se duerme entre lecturas,
            # el retraso se acumula minuto a minuto). Solo se procesa/muestra
            # uno cada `intervalo` segundos, para no saturar la UI.
            ok, frame = captura.read()
            if not ok or frame is None:
                fallos_seguidos += 1
                if fallos_seguidos > LECTURAS_FALLIDAS_PARA_RECONECTAR:
                    return False  # la captura esta degradada: se reabre de cero
                self.msleep(50)
                continue
            fallos_seguidos = 0

            if self._forzar_reconexion:
                self._forzar_reconexion = False
                return False  # resincronizacion pedida desde afuera (ej. tras un PTZ)

            if es_rtsp and (time.time() - inicio_transmision) > RESINCRONIZACION_PERIODICA_SEG:
                return False  # reconexion preventiva: pide un I-frame nuevo

            ahora = time.time()
            if ahora - ultimo_procesado < intervalo:
                continue
            ultimo_procesado = ahora

            self._buffer.append(frame.copy())
            self.frame_listo.emit(frame)
            self._actualizar_sabotaje(frame)

        return True

    def capturar_snapshot(self):
        if self._buffer:
            return self._buffer[-1].copy()
        return None
