"""Iconos propios del sidebar, dibujados con QPainter (sin archivos .svg/.png
que dependan de un plugin de Qt que podria faltar): cada uno es una funcion
chica que traza 2-4 formas simples dentro de un cuadrado, al estilo de los
iconos de la vista previa de diseno (linea fina, sin relleno salvo detalles)."""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF


def _pluma(pintor, color, ancho=1.6):
    pluma = QPen(QColor(color))
    pluma.setWidthF(ancho)
    pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
    pluma.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pintor.setPen(pluma)
    pintor.setBrush(Qt.BrushStyle.NoBrush)


def _centro_monitoreo(pintor, r, color):
    _pluma(pintor, color)
    pintor.drawEllipse(r.adjusted(2, 4, -2, -6))
    pintor.setBrush(QColor(color))
    pintor.drawEllipse(QPointF(r.center().x(), r.center().y() - 1), 2.1, 2.1)


def _incidencias(pintor, r, color):
    _pluma(pintor, color)
    triangulo = QPolygonF([
        QPointF(r.center().x(), r.top() + 2),
        QPointF(r.right() - 2, r.bottom() - 2),
        QPointF(r.left() + 2, r.bottom() - 2),
    ])
    pintor.drawPolygon(triangulo)
    pintor.drawLine(QPointF(r.center().x(), r.top() + 7.5), QPointF(r.center().x(), r.bottom() - 7.5))
    pintor.setBrush(QColor(color))
    pintor.drawEllipse(QPointF(r.center().x(), r.bottom() - 4.5), 0.9, 0.9)


def _evidencias(pintor, r, color):
    _pluma(pintor, color)
    cuerpo = QRectF(r.left() + 2, r.top() + 6, r.width() - 4, r.height() - 8)
    pintor.drawRoundedRect(cuerpo, 1.5, 1.5)
    pestana = QPolygonF([
        QPointF(cuerpo.left() + 1, cuerpo.top()),
        QPointF(cuerpo.left() + 6, cuerpo.top()),
        QPointF(cuerpo.left() + 8, cuerpo.top() - 3),
        QPointF(cuerpo.left() + 3, cuerpo.top() - 3),
    ])
    pintor.drawPolygon(pestana)


def _turnos(pintor, r, color):
    _pluma(pintor, color)
    pintor.drawEllipse(r.adjusted(2, 2, -2, -2))
    centro = r.center()
    pintor.drawLine(centro, QPointF(centro.x(), centro.y() - 4.5))
    pintor.drawLine(centro, QPointF(centro.x() + 3.2, centro.y() + 1.5))


def _radar(pintor, r, color):
    _pluma(pintor, color)
    pintor.drawEllipse(r.adjusted(2, 2, -2, -2))
    pintor.setBrush(QColor(color))
    pintor.setPen(Qt.PenStyle.NoPen)
    ancho_medio = r.width() / 2 - 2
    cuna = QRectF(r.center().x() - ancho_medio, r.center().y() - ancho_medio, ancho_medio * 2, ancho_medio * 2)
    pintor.drawPie(cuna, 45 * 16, 50 * 16)
    pintor.drawEllipse(r.center(), 1.3, 1.3)


def _camaras(pintor, r, color):
    _pluma(pintor, color)
    cuerpo = QRectF(r.left() + 1, r.top() + 6, r.width() - 6, r.height() - 10)
    pintor.drawRoundedRect(cuerpo, 2, 2)
    pintor.drawEllipse(QPointF(cuerpo.center().x() - 1, cuerpo.center().y()), 3.4, 3.4)
    visor = QPolygonF([
        QPointF(cuerpo.right(), cuerpo.top() + 1.5),
        QPointF(r.right() - 1, cuerpo.top() - 1),
        QPointF(r.right() - 1, cuerpo.bottom() + 1),
        QPointF(cuerpo.right(), cuerpo.bottom() - 1.5),
    ])
    pintor.drawPolygon(visor)


def _dvr(pintor, r, color):
    _pluma(pintor, color)
    cuerpo = QRectF(r.left() + 2, r.top() + 4, r.width() - 4, r.height() - 8)
    pintor.drawRoundedRect(cuerpo, 1.5, 1.5)
    y1 = cuerpo.top() + cuerpo.height() / 3
    y2 = cuerpo.top() + 2 * cuerpo.height() / 3
    pintor.drawLine(QPointF(cuerpo.left() + 1.5, y1), QPointF(cuerpo.right() - 1.5, y1))
    pintor.drawLine(QPointF(cuerpo.left() + 1.5, y2), QPointF(cuerpo.right() - 1.5, y2))
    pintor.setBrush(QColor(color))
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.drawEllipse(QPointF(cuerpo.right() - 2.5, cuerpo.top() + cuerpo.height() / 6), 0.9, 0.9)


def _telegram(pintor, r, color):
    _pluma(pintor, color)
    avion = QPolygonF([
        QPointF(r.left() + 2, r.center().y()),
        QPointF(r.right() - 2, r.top() + 3),
        QPointF(r.center().x() + 1, r.center().y() + 1),
        QPointF(r.right() - 5, r.bottom() - 2),
        QPointF(r.center().x() - 2, r.center().y() + 2),
        QPointF(r.left() + 2, r.center().y()),
    ])
    pintor.drawPolygon(avion)
    pintor.drawLine(QPointF(r.center().x() + 1, r.center().y() + 1), QPointF(r.right() - 2, r.top() + 3))


def _reportes(pintor, r, color):
    _pluma(pintor, color)
    base = r.bottom() - 3
    pintor.drawLine(QPointF(r.left() + 2, base), QPointF(r.right() - 2, base))
    barras = [(r.left() + 4, base - 5), (r.center().x(), base - 10), (r.right() - 5, base - 7)]
    for x, y in barras:
        pintor.drawLine(QPointF(x, base), QPointF(x, y))


def _manuales(pintor, r, color):
    _pluma(pintor, color)
    cuerpo = QRectF(r.left() + 3, r.top() + 2, r.width() - 6, r.height() - 4)
    esquina = QPolygonF([
        QPointF(cuerpo.right() - 5, cuerpo.top()),
        QPointF(cuerpo.right(), cuerpo.top()),
        QPointF(cuerpo.right(), cuerpo.top() + 5),
    ])
    pintor.drawPolygon(QPolygonF([
        QPointF(cuerpo.left(), cuerpo.top()), QPointF(cuerpo.right() - 5, cuerpo.top()),
        QPointF(cuerpo.right(), cuerpo.top() + 5), QPointF(cuerpo.right(), cuerpo.bottom()),
        QPointF(cuerpo.left(), cuerpo.bottom()),
    ]))
    for i in range(2):
        y = cuerpo.top() + 8 + i * 4.5
        pintor.drawLine(QPointF(cuerpo.left() + 3, y), QPointF(cuerpo.right() - 3, y))


def _microfono(pintor, r, color):
    _pluma(pintor, color, max(1.6, r.width() / 12))
    ancho = r.width() * 0.36
    capsula = QRectF(r.center().x() - ancho / 2, r.top() + r.height() * 0.08, ancho, r.height() * 0.52)
    pintor.setBrush(QColor(color))
    pintor.drawRoundedRect(capsula, ancho / 2, ancho / 2)
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    arco = QRectF(r.left() + r.width() * 0.2, r.top() + r.height() * 0.2, r.width() * 0.6, r.height() * 0.55)
    pintor.drawArc(arco, 200 * 16, 140 * 16)
    base_y = r.top() + r.height() * 0.76
    pintor.drawLine(QPointF(r.center().x(), base_y), QPointF(r.center().x(), r.bottom() - r.height() * 0.08))
    pintor.drawLine(
        QPointF(r.center().x() - r.width() * 0.16, r.bottom() - r.height() * 0.08),
        QPointF(r.center().x() + r.width() * 0.16, r.bottom() - r.height() * 0.08),
    )


def _copiar(pintor, r, color):
    _pluma(pintor, color)
    pintor.drawRoundedRect(QRectF(r.left() + 6, r.top() + 2, r.width() - 9, r.height() - 9), 2, 2)
    pintor.drawRoundedRect(QRectF(r.left() + 2, r.top() + 6, r.width() - 9, r.height() - 9), 2, 2)


def _flecha_abajo(pintor, r, color):
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QColor(color))
    pintor.drawPolygon(QPolygonF([
        QPointF(r.left() + r.width() * 0.15, r.top() + r.height() * 0.3),
        QPointF(r.right() - r.width() * 0.15, r.top() + r.height() * 0.3),
        QPointF(r.center().x(), r.bottom() - r.height() * 0.25),
    ]))


_DIBUJANTES = {
    "microfono": _microfono,
    "copiar": _copiar,
    "flecha_abajo": _flecha_abajo,
    "dashboard": _centro_monitoreo,
    "incidencias": _incidencias,
    "evidencias": _evidencias,
    "turnos": _turnos,
    "radar": _radar,
    "camaras": _camaras,
    "dvr": _dvr,
    "telegram": _telegram,
    "reportes": _reportes,
    "manuales": _manuales,
}


def pixmap_icono(nombre, color="#ffffff", tamano=20):
    dibujante = _DIBUJANTES.get(nombre)
    pixmap = QPixmap(tamano, tamano)
    pixmap.fill(Qt.GlobalColor.transparent)
    if dibujante is not None:
        pintor = QPainter(pixmap)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        dibujante(pintor, QRectF(0, 0, tamano, tamano), color)
        pintor.end()
    return pixmap


def icono(nombre, color="#ffffff", tamano=20):
    """QIcon dibujado en el momento (no viene de un archivo): `color` admite
    cualquier string que entienda QColor (ej. "#8b94a3" inactivo, "#36d6c9"
    activo), asi el mismo icono sirve para los dos estados del boton."""
    return QIcon(pixmap_icono(nombre, color, tamano))
