import queue
import time

from PyQt6.QtCore import QThread, pyqtSignal

SEGUNDOS_SOSTENIDO = 3.0
MIN_MANOS_ARRIBA = 1          # basta una mano (senal de auxilio) o dos (manos arriba)
UMBRAL_ALTURA_MUNECA = 0.6    # normalizado 0..1 (0 = arriba de la imagen); 0.6 = mitad superior holgada
TOLERANCIA_PARPADEO_SEG = 1.0  # tolera cortes breves de deteccion sin reiniciar el conteo

DISPONIBLE = True
try:
    import mediapipe as mp
except ImportError:
    DISPONIBLE = False


class DetectorPanicoThread(QThread):
    """Analiza frames de una camara (QThread aparte, no bloquea la UI) buscando el
    gesto de 'mano(s) arriba' sostenido SEGUNDOS_SOSTENIDO segundos (modo panico
    silencioso, sin botones fisicos)."""

    gesto_detectado = pyqtSignal()
    no_disponible = pyqtSignal(str)
    progreso = pyqtSignal(bool, float)  # detectando_ahora, segundos_sostenidos

    def __init__(self, parent=None):
        super().__init__(parent)
        self._activo = True
        self._cola = queue.Queue(maxsize=2)
        self._inicio_gesto = None
        self._ultima_deteccion = 0.0
        self._ultimo_disparo = 0.0

    def detener(self):
        self._activo = False

    def alimentar_frame(self, frame):
        """Llamado (desde cualquier hilo) con el ultimo frame de la camara de Ingreso."""
        if self._cola.full():
            try:
                self._cola.get_nowait()
            except queue.Empty:
                pass
        try:
            self._cola.put_nowait(frame)
        except queue.Full:
            pass

    def _manos_arriba(self, resultado):
        if not resultado.multi_hand_landmarks:
            return False
        manos_arriba = 0
        for mano in resultado.multi_hand_landmarks:
            # promedio de toda la mano (no solo la muneca): mas tolerante a la
            # orientacion de la palma y a manos parcialmente fuera de cuadro
            promedio_y = sum(p.y for p in mano.landmark) / len(mano.landmark)
            if promedio_y < UMBRAL_ALTURA_MUNECA:
                manos_arriba += 1
        return manos_arriba >= MIN_MANOS_ARRIBA

    def run(self):
        if not DISPONIBLE:
            self.no_disponible.emit("mediapipe no esta instalado: use el boton manual de Modo Panico.")
            return

        import cv2

        try:
            manos = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        except Exception as exc:
            self.no_disponible.emit(f"No se pudo iniciar el detector de gestos: {exc}")
            return

        while self._activo:
            try:
                frame = self._cola.get(timeout=0.5)
            except queue.Empty:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            resultado = manos.process(rgb)

            ahora = time.time()
            detectado = self._manos_arriba(resultado)

            if detectado:
                self._ultima_deteccion = ahora
                if self._inicio_gesto is None:
                    self._inicio_gesto = ahora
            elif self._inicio_gesto is not None and (ahora - self._ultima_deteccion) > TOLERANCIA_PARPADEO_SEG:
                # solo se reinicia el conteo si el corte en la deteccion fue largo
                # (mediapipe puede parpadear frame a frame sin que la persona
                # haya bajado la mano realmente)
                self._inicio_gesto = None

            transcurrido = (ahora - self._inicio_gesto) if self._inicio_gesto else 0.0
            self.progreso.emit(detectado, min(transcurrido, SEGUNDOS_SOSTENIDO))

            if self._inicio_gesto and transcurrido >= SEGUNDOS_SOSTENIDO and (ahora - self._ultimo_disparo) > 20:
                self._ultimo_disparo = ahora
                self._inicio_gesto = None
                self.gesto_detectado.emit()

        manos.close()
