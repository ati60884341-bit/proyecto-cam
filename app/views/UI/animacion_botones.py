from PyQt6.QtCore import QEvent, QObject, QPropertyAnimation
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QPushButton

DURACION_MS = 120
OPACIDAD_HOVER = 0.82


class AnimadorHoverBotones(QObject):
    """Filtro de eventos instalado UNA sola vez a nivel de QApplication (ver
    app/main.py): asi TODOS los QPushButton del programa -sin importar en
    que pestana/archivo esten- se atenuan suavemente al pasar el mouse, en
    vez de quedarse "muertos" con el cambio de color instantaneo que ya da
    la hoja de estilos (tema.py). No hace falta tocar cada vista para
    agregar esto - por diseno, un boton que ya use su propio QGraphicsEffect
    (ninguno en el programa hoy) quedaria afuera, pero esa combinacion no
    se da en ningun lado todavia."""

    def eventFilter(self, obj, event):
        if isinstance(obj, QPushButton) and obj.isEnabled():
            if event.type() == QEvent.Type.Enter:
                self._animar(obj, 1.0, OPACIDAD_HOVER, quitar_al_final=False)
            elif event.type() == QEvent.Type.Leave:
                self._animar(obj, OPACIDAD_HOVER, 1.0, quitar_al_final=True)
        return False

    def _animar(self, boton, inicio, fin, quitar_al_final):
        efecto = QGraphicsOpacityEffect(boton)
        boton.setGraphicsEffect(efecto)
        animacion = QPropertyAnimation(efecto, b"opacity", boton)
        animacion.setDuration(DURACION_MS)
        animacion.setStartValue(inicio)
        animacion.setEndValue(fin)
        if quitar_al_final:
            animacion.finished.connect(lambda: boton.setGraphicsEffect(None))
        animacion.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        boton._animacion_hover_activa = animacion  # evita que el GC la corte a mitad de camino
