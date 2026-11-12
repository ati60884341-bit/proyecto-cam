"""Pantalla de radar: barrido giratorio mientras se busca y un punto por
cada equipo encontrado (en una posicion fija derivada de su IP)."""
import math
import zlib

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QConicalGradient, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QSizePolicy, QWidget

TEAL = QColor("#36d6c9")


class RadarAnimado(QWidget):
    PASO_GRADOS = 4
    INTERVALO_MS = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(240)
        self.setFixedHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._angulo = 90.0
        self._puntos = {}  # clave -> (angulo, radio 0..1)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._avanzar)

    def iniciar(self):
        self._puntos.clear()
        self._timer.start(self.INTERVALO_MS)
        self.update()

    def detener(self):
        self._timer.stop()
        self.update()

    def agregar_punto(self, clave):
        h = zlib.crc32(clave.encode())
        self._puntos[clave] = (h % 360, 0.3 + (h >> 9) % 60 / 100)
        self.update()

    def _avanzar(self):
        self._angulo = (self._angulo + self.PASO_GRADOS) % 360
        self.update()

    def paintEvent(self, _evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        lado = min(self.width(), self.height()) - 10
        radio = lado / 2
        centro = QPointF(self.width() / 2, self.height() / 2)
        circulo = QRectF(centro.x() - radio, centro.y() - radio, lado, lado)

        fondo = QRadialGradient(centro, radio)
        fondo.setColorAt(0, QColor(12, 40, 44))
        fondo.setColorAt(1, QColor(8, 18, 24))
        pintor.setBrush(fondo)
        pintor.setPen(QPen(QColor(54, 214, 201, 150), 2))
        pintor.drawEllipse(circulo)

        anillo = QPen(QColor(54, 214, 201, 55), 1)
        pintor.setPen(anillo)
        pintor.setBrush(Qt.BrushStyle.NoBrush)
        for fraccion in (0.25, 0.5, 0.75):
            pintor.drawEllipse(centro, radio * fraccion, radio * fraccion)
        pintor.drawLine(QPointF(centro.x() - radio, centro.y()), QPointF(centro.x() + radio, centro.y()))
        pintor.drawLine(QPointF(centro.x(), centro.y() - radio), QPointF(centro.x(), centro.y() + radio))

        buscando = self._timer.isActive()
        if buscando:
            # estela: opaca en el borde que avanza y se desvanece hacia atras
            estela = QConicalGradient(centro, self._angulo)
            estela.setColorAt(0.0, QColor(54, 214, 201, 0))
            estela.setColorAt(0.80, QColor(54, 214, 201, 0))
            estela.setColorAt(1.0, QColor(54, 214, 201, 150))
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(estela)
            pintor.drawEllipse(circulo)
            rad = math.radians(self._angulo)
            pintor.setPen(QPen(TEAL, 2))
            pintor.drawLine(centro, QPointF(centro.x() + radio * math.cos(rad), centro.y() - radio * math.sin(rad)))

        for angulo, distancia in self._puntos.values():
            rad = math.radians(angulo)
            punto = QPointF(centro.x() + radio * distancia * math.cos(rad), centro.y() - radio * distancia * math.sin(rad))
            # el punto se ilumina cuando el barrido pasa y se apaga despacio
            atraso = (self._angulo - angulo) % 360 if buscando else 0
            alfa = max(90, int(255 - atraso * 0.9))
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(QColor(54, 214, 201, alfa // 3))
            pintor.drawEllipse(punto, 11, 11)
            pintor.setBrush(QColor(140, 255, 245, alfa))
            pintor.drawEllipse(punto, 5, 5)

        pintor.setBrush(TEAL)
        pintor.drawEllipse(centro, 3, 3)
        pintor.end()
