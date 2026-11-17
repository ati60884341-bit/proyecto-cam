"""Mapa del lugar: plano del local con las camaras ubicadas encima.

- Cada camara se arrastra con el mouse hasta donde esta en la realidad.
- La camara que ve movimiento se enciende (anillo que late).
- Cuando el movimiento pasa de una camara a otra, un punto luminoso viaja
  por el plano de una a la otra y queda una linea de "recorrido" que se
  engrosa con cada paso repetido.
- "Mapa de calor": manchas en cada camara segun cuanto movimiento vio.
"""
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from app.views.UI.tema import COLOR_ACENTO, COLOR_ACENTO_SECUNDARIO, COLOR_TEXTO_MUTED

TEAL = QColor(COLOR_ACENTO)
NARANJA = QColor(COLOR_ACENTO_SECUNDARIO)
RADIO_CAMARA = 17
DURACION_PASO_SEG = 1.4


def _curva(a, b):
    """Curva suave a->b (bezier cuadratica). Se dobla hacia un costado, asi
    los recorridos A->B y B->A quedan como dos lineas separadas."""
    medio = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
    dx, dy = b.x() - a.x(), b.y() - a.y()
    control = QPointF(medio.x() - dy * 0.18, medio.y() + dx * 0.18)
    return control


def _punto_en_curva(a, c, b, t):
    u = 1 - t
    return QPointF(u * u * a.x() + 2 * u * t * c.x() + t * t * b.x(),
                   u * u * a.y() + 2 * u * t * c.y() + t * t * b.y())


class LienzoMapa(QWidget):
    posicion_cambiada = Signal(str, float, float)   # clave, x, y en 0..1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.camaras = {}        # clave -> {"nombre": str, "pos": (x, y)}
        self.activas = set()
        self.calor = {}
        self.flujos = {}
        self.mostrar_calor = True
        self.plano = None        # QPixmap o None
        self._animaciones = []   # [(origen, destino, t0)]
        self.personas_vivas = {}  # camara -> (t, [((x, y), rgb_arriba, rgb_abajo)]) de la IA calibrada
        self._arrastrando = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)

    # ---- datos ----
    def set_camaras(self, camaras):
        self.camaras = camaras
        sin_lugar = [c for c in camaras.values() if c.get("pos") is None]
        for i, cam in enumerate(sin_lugar):
            # todavia no ubicadas: en fila en la parte de abajo, para arrastrarlas
            cam["pos"] = ((i + 1) / (len(sin_lugar) + 1), 0.9)
        self.update()

    def animar_paso(self, origen, destino):
        self._animaciones.append((origen, destino, time.time()))

    # ---- animacion solo con la pestana a la vista (no gasta CPU de las camaras) ----
    def showEvent(self, evento):
        self._timer.start(33)
        super().showEvent(evento)

    def hideEvent(self, evento):
        self._timer.stop()
        super().hideEvent(evento)

    # ---- geometria ----
    def _area(self):
        margen = 12
        r = QRectF(margen, margen, self.width() - 2 * margen, self.height() - 2 * margen)
        if self.plano and not self.plano.isNull():
            escala = min(r.width() / self.plano.width(), r.height() / self.plano.height())
            w, h = self.plano.width() * escala, self.plano.height() * escala
            return QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h)
        return r

    def _punto(self, clave, area):
        x, y = self.camaras[clave]["pos"]
        return QPointF(area.left() + x * area.width(), area.top() + y * area.height())

    # ---- arrastrar camaras ----
    def _camara_en(self, pos):
        area = self._area()
        for clave in reversed(list(self.camaras)):
            p = self._punto(clave, area)
            if math.hypot(p.x() - pos.x(), p.y() - pos.y()) <= RADIO_CAMARA + 4:
                return clave
        return None

    def mousePressEvent(self, evento):
        self._arrastrando = self._camara_en(evento.position())
        if self._arrastrando:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, evento):
        if self._arrastrando:
            area = self._area()
            x = min(1.0, max(0.0, (evento.position().x() - area.left()) / area.width()))
            y = min(1.0, max(0.0, (evento.position().y() - area.top()) / area.height()))
            self.camaras[self._arrastrando]["pos"] = (x, y)
            self.update()
        elif self._camara_en(evento.position()):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, _evento):
        if self._arrastrando:
            x, y = self.camaras[self._arrastrando]["pos"]
            self.posicion_cambiada.emit(self._arrastrando, x, y)
            self._arrastrando = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    # ---- dibujo ----
    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0d1118"))
        area = self._area()
        ahora = time.time()

        if self.plano and not self.plano.isNull():
            p.setOpacity(0.85)
            p.drawPixmap(area.toRect(), self.plano)
            p.setOpacity(1.0)
        else:
            self._dibujar_cuadricula(p, area)

        camaras = [c for c in self.camaras if self.camaras[c].get("pos") is not None]
        if self.mostrar_calor:
            self._dibujar_calor(p, area, camaras)
        self._dibujar_flujos(p, area)
        self._dibujar_animaciones(p, area, ahora)
        self._dibujar_personas(p, area, ahora)
        for clave in camaras:
            self._dibujar_camara(p, area, clave, ahora)
        p.end()

    def _dibujar_cuadricula(self, p, area):
        p.setPen(QPen(QColor(54, 214, 201, 22), 1))
        paso = 32
        x = area.left()
        while x <= area.right():
            p.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
            x += paso
        y = area.top()
        while y <= area.bottom():
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            y += paso
        p.setPen(QPen(QColor(54, 214, 201, 70), 1.5, Qt.PenStyle.DashLine))
        p.drawRoundedRect(area, 8, 8)
        p.setPen(QColor(COLOR_TEXTO_MUTED))
        p.drawText(area.adjusted(0, 18, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   "Cargue el plano del lugar y arrastre cada camara a su posicion")

    def _dibujar_calor(self, p, area, camaras):
        maximo = max((self.calor.get(c, 0) for c in camaras), default=0)
        if maximo <= 0:
            return
        for clave in camaras:
            valor = self.calor.get(clave, 0)
            if valor <= 0:
                continue
            k = math.sqrt(valor / maximo)
            centro = self._punto(clave, area)
            radio = min(area.width(), area.height()) * (0.07 + 0.16 * k)
            grad = QRadialGradient(centro, radio)
            grad.setColorAt(0.0, QColor(255, 60, 40, int(200 * k + 30)))
            grad.setColorAt(0.45, QColor(255, 190, 0, int(120 * k + 15)))
            grad.setColorAt(1.0, QColor(255, 190, 0, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(grad)
            p.drawEllipse(centro, radio, radio)

    def _dibujar_flujos(self, p, area):
        if not self.flujos:
            return
        maximo = max(self.flujos.values())
        fuente = QFont(self.font())
        fuente.setPointSize(8)
        fuente.setBold(True)
        p.setFont(fuente)
        for (origen, destino), cantidad in self.flujos.items():
            if origen not in self.camaras or destino not in self.camaras:
                continue
            a, b = self._punto(origen, area), self._punto(destino, area)
            c = _curva(a, b)
            camino = QPainterPath(a)
            camino.quadTo(c, b)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(54, 214, 201, 70 + int(120 * cantidad / maximo)),
                          1.5 + 5 * cantidad / maximo, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawPath(camino)
            # punta de flecha cerca del destino
            t1, t2 = _punto_en_curva(a, c, b, 0.78), _punto_en_curva(a, c, b, 0.84)
            ang = math.atan2(t2.y() - t1.y(), t2.x() - t1.x())
            for desvio in (2.6, -2.6):
                p.drawLine(t2, QPointF(t2.x() + 9 * math.cos(ang + desvio), t2.y() + 9 * math.sin(ang + desvio)))
            medio = _punto_en_curva(a, c, b, 0.5)
            etiqueta = QRectF(medio.x() - 11, medio.y() - 9, 22, 18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(13, 17, 24, 220))
            p.drawRoundedRect(etiqueta, 9, 9)
            p.setPen(TEAL)
            p.drawText(etiqueta, Qt.AlignmentFlag.AlignCenter, str(cantidad))

    def _dibujar_animaciones(self, p, area, ahora):
        vivas = []
        for origen, destino, t0 in self._animaciones:
            avance = (ahora - t0) / DURACION_PASO_SEG
            if avance >= 1.0 or origen not in self.camaras or destino not in self.camaras:
                continue
            vivas.append((origen, destino, t0))
            a, b = self._punto(origen, area), self._punto(destino, area)
            c = _curva(a, b)
            suave = 1 - (1 - avance) ** 3  # arranca rapido y frena al llegar
            for i in range(10, 0, -1):    # estela
                t = max(0.0, suave - i * 0.025)
                q = _punto_en_curva(a, c, b, t)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 210, 120, int(130 * (1 - i / 10))))
                p.drawEllipse(q, 7 - i * 0.4, 7 - i * 0.4)
            q = _punto_en_curva(a, c, b, suave)
            brillo = QRadialGradient(q, 26)
            brillo.setColorAt(0, QColor(255, 240, 200, 255))
            brillo.setColorAt(0.3, QColor(255, 170, 60, 220))
            brillo.setColorAt(1, QColor(255, 120, 0, 0))
            p.setBrush(brillo)
            p.drawEllipse(q, 26, 26)
        self._animaciones = vivas

    def _dibujar_personas(self, p, area, ahora):
        """Un punto por persona, mitad de arriba con el color de su ropa de
        arriba y mitad de abajo con el de abajo. Se borra solo si la IA de esa
        camara deja de mandar datos (camara apagada o sin gente)."""
        for clave, (t, puntos) in list(self.personas_vivas.items()):
            if ahora - t > 1.5:
                del self.personas_vivas[clave]
                continue
            for (x, y), arriba, abajo in puntos:
                c = QPointF(area.left() + x * area.width(), area.top() + y * area.height())
                halo = QRadialGradient(c, 24)
                halo.setColorAt(0, QColor(60, 220, 60, 150))
                halo.setColorAt(1, QColor(60, 220, 60, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(halo)
                p.drawEllipse(c, 24, 24)
                r = 9
                caja = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
                p.setBrush(QColor(*arriba))
                p.drawPie(caja, 0, 180 * 16)
                p.setBrush(QColor(*abajo))
                p.drawPie(caja, 180 * 16, 180 * 16)
                p.setPen(QPen(QColor(60, 220, 60), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(caja)

    def _dibujar_camara(self, p, area, clave, ahora):
        centro = self._punto(clave, area)
        activa = clave in self.activas
        if activa:
            fase = (ahora * 1.6) % 1.0  # anillo que se expande y se desvanece
            p.setPen(QPen(QColor(255, 120, 60, int(220 * (1 - fase))), 2.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            radio = RADIO_CAMARA + 4 + fase * 22
            p.drawEllipse(centro, radio, radio)
        p.setPen(QPen(NARANJA if activa else TEAL, 2.5))
        p.setBrush(QColor(80, 30, 15) if activa else QColor(16, 30, 36))
        p.drawEllipse(centro, RADIO_CAMARA, RADIO_CAMARA)
        # camarita dibujada adentro
        color = NARANJA if activa else TEAL
        p.setPen(QPen(color, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cuerpo = QRectF(centro.x() - 8, centro.y() - 5, 12, 10)
        p.drawRoundedRect(cuerpo, 2, 2)
        p.drawLine(QPointF(centro.x() + 4, centro.y() - 1), QPointF(centro.x() + 9, centro.y() - 4))
        p.drawLine(QPointF(centro.x() + 4, centro.y() + 1), QPointF(centro.x() + 9, centro.y() + 4))
        p.drawLine(QPointF(centro.x() + 9, centro.y() - 4), QPointF(centro.x() + 9, centro.y() + 4))

        nombre = self.camaras[clave]["nombre"]
        fuente = QFont(self.font())
        fuente.setPointSize(9)
        fuente.setBold(activa)
        p.setFont(fuente)
        ancho = p.fontMetrics().horizontalAdvance(nombre) + 14
        caja = QRectF(centro.x() - ancho / 2, centro.y() + RADIO_CAMARA + 5, ancho, 19)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(13, 17, 24, 215))
        p.drawRoundedRect(caja, 9, 9)
        p.setPen(QColor("#ffffff") if activa else QColor("#d7dde5"))
        p.drawText(caja, Qt.AlignmentFlag.AlignCenter, nombre)


class MapaView(QWidget):
    plano_elegido = Signal(str)
    reiniciar_pedido = Signal()
    mostrada = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(18, 14, 18, 14)

        cabecera = QHBoxLayout()
        titulo = QLabel("Mapa del lugar")
        titulo.setStyleSheet("font-size: 20px; font-weight: 600; color: white;")
        cabecera.addWidget(titulo)
        subtitulo = QLabel("recorrido de las personas entre camaras, en vivo")
        subtitulo.setStyleSheet(f"color: {COLOR_TEXTO_MUTED};")
        cabecera.addWidget(subtitulo)
        cabecera.addStretch()
        self.chk_calor = QCheckBox("Mapa de calor")
        self.chk_calor.setChecked(True)
        cabecera.addWidget(self.chk_calor)
        btn_plano = QPushButton("Cargar plano...")
        btn_plano.setToolTip("Una foto o dibujo del local visto desde arriba (PNG o JPG)")
        btn_plano.clicked.connect(self._elegir_plano)
        cabecera.addWidget(btn_plano)
        btn_reiniciar = QPushButton("Reiniciar recorrido")
        btn_reiniciar.clicked.connect(self.reiniciar_pedido.emit)
        cabecera.addWidget(btn_reiniciar)
        raiz.addLayout(cabecera)

        cuerpo = QHBoxLayout()
        self.lienzo = LienzoMapa()
        self.chk_calor.toggled.connect(self._alternar_calor)
        cuerpo.addWidget(self.lienzo, stretch=1)

        lateral = QFrame()
        lateral.setFixedWidth(250)
        lateral.setStyleSheet("QFrame { background: #171b24; border: 1px solid #2a303c; border-radius: 10px; }")
        col = QVBoxLayout(lateral)
        lbl = QLabel("Recorrido en vivo")
        lbl.setStyleSheet("color: white; font-weight: 600; border: none;")
        col.addWidget(lbl)
        self.lista_pasos = QListWidget()
        self.lista_pasos.setStyleSheet("border: none; background: transparent;")
        col.addWidget(self.lista_pasos, stretch=1)
        self.lbl_resumen = QLabel()
        self.lbl_resumen.setWordWrap(True)
        self.lbl_resumen.setStyleSheet(f"color: {COLOR_TEXTO_MUTED}; border: none; font-size: 11px;")
        col.addWidget(self.lbl_resumen)
        ayuda = QLabel(
            "Arrastre cada camara a su lugar en el plano. Cuando alguien camina de una "
            "zona a otra, el punto naranja viaja entre las camaras y la linea se va "
            "engrosando con cada paso."
        )
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet(f"color: {COLOR_TEXTO_MUTED}; border: none; font-size: 11px;")
        col.addWidget(ayuda)
        cuerpo.addWidget(lateral)
        raiz.addLayout(cuerpo, stretch=1)
        self.limpiar()

    def showEvent(self, evento):
        self.mostrada.emit()
        super().showEvent(evento)

    def _alternar_calor(self, activo):
        self.lienzo.mostrar_calor = activo
        self.lienzo.update()

    def _elegir_plano(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Plano del lugar", "", "Imagenes (*.png *.jpg *.jpeg *.bmp)")
        if ruta:
            self.plano_elegido.emit(ruta)

    def set_plano(self, ruta):
        pixmap = QPixmap(ruta) if ruta else None
        self.lienzo.plano = pixmap if pixmap and not pixmap.isNull() else None
        self.lienzo.update()

    def agregar_paso(self, texto):
        self.lista_pasos.insertItem(0, texto)
        while self.lista_pasos.count() > 100:
            self.lista_pasos.takeItem(self.lista_pasos.count() - 1)

    def set_resumen(self, texto):
        self.lbl_resumen.setText(texto)

    def limpiar(self):
        self.lista_pasos.clear()
        self.lbl_resumen.setText("Todavia no hubo pasos entre camaras.")
