import math
import os
import random

from PyQt6.QtCore import Qt, QTimer, QRectF, QLineF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QMovie
from PyQt6.QtWidgets import QFrame

from app.config import IMAGENES_DIR

_RUTA_IMAGEN_ESTATICA = os.path.join(IMAGENES_DIR, "fondo_nocturno.png")
_RUTA_IMAGEN_ANIMADA = os.path.join(IMAGENES_DIR, "fondo_nocturno.gif")
_pixmap_original = None  # cache a nivel de modulo: una sola carga para toda la app


def _cargar_pixmap_estatico():
    global _pixmap_original
    if _pixmap_original is None:
        _pixmap_original = QPixmap(_RUTA_IMAGEN_ESTATICA)
    return _pixmap_original


def _recortar_a_tamano(fuente, tamano):
    """Escala `fuente` para que CUBRA `tamano` (sin deformar) y recorta el
    sobrante centrado - lo mismo que "cover" en CSS: nunca se ve una franja
    vacia ni la imagen estirada, sin importar la proporcion del widget."""
    escalado = fuente.scaled(
        tamano, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation,
    )
    x = (escalado.width() - tamano.width()) // 2
    y = (escalado.height() - tamano.height()) // 2
    return escalado.copy(x, y, tamano.width(), tamano.height())


class FondoNocturno(QFrame):
    """Fondo con la escena nocturna (colinas, luna, lluvia de meteoros) que
    da la identidad visual de CAM.

    animado=True (splash, login): reproduce el GIF original
    (fondo_nocturno.gif, el mismo que mando el usuario) cuadro por cuadro
    via QMovie - la lluvia de meteoros real, no una recreacion. Encima se
    dibuja una capa propia de estrellas que titilan y pasto que se balancea
    con el viento, porque esas partes de la foto original quedan quietas y
    sin eso se notaba la mezcla "mitad animado, mitad quieto".

    animado=False (sidebar de MainWindow): una sola foto fija (el primer
    cuadro, pre-exportado a .png) y nada de QMovie ni temporizador - a
    proposito, para no competir por CPU/GPU con los hilos de video de cada
    camara en vivo (ver camera_service.py). Una escena quieta cuesta un
    solo repintado, no 15-30 por segundo.

    opacidad_superposicion: 0 (imagen pura) a 1 (casi negro) - controla
    cuanto se oscurece la imagen para que el texto/tarjetas de encima sigan
    siendo legibles."""

    INTERVALO_TIMER_MS = 60
    CANTIDAD_ESTRELLAS = 70
    CANTIDAD_BRIZNAS = 22
    MAX_METEOROS_SIMULTANEOS = 3

    def __init__(self, parent=None, animado=True, opacidad_superposicion=0.35):
        super().__init__(parent)
        self.animado = animado
        self.opacidad_superposicion = opacidad_superposicion
        self._pixmap_recortado = None
        self._tiempo_ms = 0
        self._meteoros = []
        self._pelicula = None
        self._rng = random.Random(7)  # semilla fija: el patron de estrellas no "salta" entre redibujados
        self._estrellas = [
            {
                "xf": self._rng.uniform(0.0, 1.0),
                "yf": self._rng.uniform(0.0, 0.55),
                "r": self._rng.uniform(0.6, 1.8),
                "fase": self._rng.uniform(0.0, 2 * math.pi),
                "vel": self._rng.uniform(1.1, 2.2),
            }
            for _ in range(self.CANTIDAD_ESTRELLAS)
        ]
        # briznas de pasto/follaje al pie de la escena: no es parte de la
        # foto/GIF (esa parte queda quieta), es una capa propia encima que
        # se balancea con el viento - funciona igual sin importar que parte
        # quedo recortada abajo, porque se ancla al borde del widget, no a
        # un pixel fijo de la imagen
        self._briznas = [
            {
                "xf": (i + self._rng.uniform(0.15, 0.85)) / self.CANTIDAD_BRIZNAS,
                "alto": self._rng.uniform(10, 22),
                "fase": self._rng.uniform(0.0, 2 * math.pi),
                "vel": self._rng.uniform(0.9, 1.5),
            }
            for i in range(self.CANTIDAD_BRIZNAS)
        ]

        if self.animado:
            self._pelicula = QMovie(_RUTA_IMAGEN_ANIMADA)
            if self._pelicula.isValid():
                self._pelicula.frameChanged.connect(lambda _n: self.update())
            else:
                self._pelicula = None  # sin GIF valido: respaldo = foto fija + meteoros propios

            self._temporizador = QTimer(self)
            self._temporizador.timeout.connect(self._avanzar)
            self._temporizador.start(self.INTERVALO_TIMER_MS)

    def _avanzar(self):
        self._tiempo_ms += self.INTERVALO_TIMER_MS
        if self._pelicula is None:
            # sin el GIF real (ej. no se empaqueto el .gif): se mantienen
            # los meteoros propios como respaldo, para no quedar sin lluvia
            if len(self._meteoros) < self.MAX_METEOROS_SIMULTANEOS and self._rng.random() < 0.045:
                self._meteoros.append({
                    "x0": self._rng.uniform(0.05, 0.9) * max(self.width(), 1),
                    "y0": self._rng.uniform(0.0, 0.22) * max(self.height(), 1),
                    "inicio": self._tiempo_ms,
                    "duracion": self._rng.uniform(800, 1500),
                })
            self._meteoros = [
                m for m in self._meteoros if (self._tiempo_ms - m["inicio"]) < m["duracion"]
            ]
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._pixmap_recortado = None  # se recalcula perezosamente en el proximo paintEvent

    def showEvent(self, event):
        super().showEvent(event)
        if self._pelicula is not None and self._pelicula.state() != QMovie.MovieState.Running:
            self._pelicula.start()
        if self.animado and not self._temporizador.isActive():
            self._temporizador.start(self.INTERVALO_TIMER_MS)

    def hideEvent(self, event):
        super().hideEvent(event)
        # splash/login se cierran apenas se entra al programa; sin esto el
        # GIF seguiria decodificando cuadros de fondo (CPU) el resto de la
        # sesion, aunque la ventana ya no se vea
        if self._pelicula is not None:
            self._pelicula.stop()
        if self.animado:
            self._temporizador.stop()

    def _pixmap_estatico_para(self, tamano):
        """Usado solo cuando animado=False (sidebar): con cache, porque la
        escena no cambia de un repintado a otro."""
        original = _cargar_pixmap_estatico()
        if original.isNull():
            return None
        if self._pixmap_recortado is not None and self._pixmap_recortado.size() == tamano:
            return self._pixmap_recortado
        self._pixmap_recortado = _recortar_a_tamano(original, tamano)
        return self._pixmap_recortado

    def _pixmap_cuadro_actual(self, tamano):
        """Usado cuando animado=True: se guarda solo el ultimo cuadro escalado.
        Las estrellas repintan ~16 veces por segundo y el GIF cambia menos:
        reescalar el mismo cuadro a pantalla completa cada vez era lo caro."""
        if self._pelicula is None:
            return self._pixmap_estatico_para(tamano)
        clave = (self._pelicula.currentFrameNumber(), tamano.width(), tamano.height())
        if getattr(self, "_cache_cuadro", (None, None))[0] == clave:
            return self._cache_cuadro[1]
        fuente = self._pelicula.currentPixmap()
        if fuente.isNull():
            return self._pixmap_estatico_para(tamano)
        self._cache_cuadro = (clave, _recortar_a_tamano(fuente, tamano))
        return self._cache_cuadro[1]

    def paintEvent(self, event):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        if self.animado:
            pixmap = self._pixmap_cuadro_actual(rect.size())
        else:
            pixmap = self._pixmap_estatico_para(rect.size())

        if pixmap is not None:
            pintor.drawPixmap(0, 0, pixmap)
        else:
            pintor.fillRect(rect, QColor("#0c0e13"))

        alpha = int(255 * self.opacidad_superposicion)
        pintor.fillRect(rect, QColor(8, 10, 16, alpha))

        if self.animado:
            self._dibujar_estrellas(pintor, rect)
            if self._pelicula is None:
                self._dibujar_meteoros(pintor, rect)  # respaldo, sin GIF real
            self._dibujar_pasto(pintor, rect)

        pintor.end()

    def _dibujar_estrellas(self, pintor, rect):
        tiempo_seg = self._tiempo_ms / 1000.0
        pintor.setPen(Qt.PenStyle.NoPen)
        for estrella in self._estrellas:
            alpha = 0.25 + 0.75 * abs(math.sin(tiempo_seg * estrella["vel"] + estrella["fase"]))
            pintor.setBrush(QColor(255, 255, 255, int(255 * alpha)))
            x = estrella["xf"] * rect.width()
            y = estrella["yf"] * rect.height()
            r = estrella["r"]
            pintor.drawEllipse(QRectF(x - r, y - r, r * 2, r * 2))

    def _dibujar_meteoros(self, pintor, rect):
        for meteoro in self._meteoros:
            t = (self._tiempo_ms - meteoro["inicio"]) / meteoro["duracion"]
            t = max(0.0, min(1.0, t))
            alpha = (t / 0.15) if t < 0.15 else (1.0 - (t - 0.75) / 0.25 if t > 0.75 else 1.0)
            alpha = max(0.0, min(1.0, alpha))
            cabeza_x = meteoro["x0"] + t * rect.width() * 0.4
            cabeza_y = meteoro["y0"] + t * rect.width() * 0.4 * 0.62
            cola_x = cabeza_x - 80
            cola_y = cabeza_y - 50
            pluma = QPen(QColor(255, 255, 255, int(220 * alpha)))
            pluma.setWidthF(1.4)
            pintor.setPen(pluma)
            pintor.drawLine(QLineF(cola_x, cola_y, cabeza_x, cabeza_y))

    def _dibujar_pasto(self, pintor, rect):
        tiempo_seg = self._tiempo_ms / 1000.0
        pluma = QPen(QColor(5, 6, 10, 165))
        pluma.setWidthF(1.6)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        pintor.setPen(pluma)
        base_y = rect.bottom() + 1
        for brizna in self._briznas:
            balanceo = math.sin(tiempo_seg * brizna["vel"] + brizna["fase"]) * 5.0
            x0 = brizna["xf"] * rect.width()
            pintor.drawLine(QLineF(x0, base_y, x0 + balanceo, base_y - brizna["alto"]))
