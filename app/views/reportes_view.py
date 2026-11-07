from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from app.views.UI.tema import (
    COLOR_FONDO, COLOR_PANEL, COLOR_BORDE, COLOR_TEXTO, COLOR_TEXTO_MUTED,
    COLOR_ACENTO, COLOR_ACENTO_SECUNDARIO,
)


class ReportesView(QWidget):
    refrescar_solicitado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        encabezado = QHBoxLayout()
        encabezado.addWidget(QLabel("Reportes de incidencias"))
        btn_refrescar = QPushButton("Actualizar")
        btn_refrescar.clicked.connect(self.refrescar_solicitado.emit)
        encabezado.addWidget(btn_refrescar)
        layout.addLayout(encabezado)

        # colores a juego con el resto del programa (tema.py) en vez del
        # blanco por defecto de matplotlib, que desentonaba con todo lo demas
        self.figura = Figure(figsize=(8, 5), facecolor=COLOR_FONDO)
        self.canvas = FigureCanvasQTAgg(self.figura)
        self.canvas.setStyleSheet(f"background-color: {COLOR_FONDO};")
        layout.addWidget(self.canvas)

    def _estilizar_eje(self, ax, titulo):
        ax.set_facecolor(COLOR_PANEL)
        ax.set_title(titulo, color=COLOR_TEXTO, fontsize=11)
        ax.tick_params(axis="x", rotation=30, colors=COLOR_TEXTO_MUTED)
        ax.tick_params(axis="y", colors=COLOR_TEXTO_MUTED)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        for lado in ("left", "bottom"):
            ax.spines[lado].set_color(COLOR_BORDE)
        ax.yaxis.grid(True, color=COLOR_BORDE, linewidth=0.6, alpha=0.6)
        ax.set_axisbelow(True)

    def actualizar_graficos(self, por_tipo, por_zona):
        self.figura.clear()

        ax1 = self.figura.add_subplot(1, 2, 1)
        if por_tipo:
            ax1.bar(
                [r["Tipo"] for r in por_tipo], [r["Total"] for r in por_tipo],
                color=COLOR_ACENTO, edgecolor=COLOR_ACENTO, linewidth=0,
            )
        self._estilizar_eje(ax1, "Incidencias por tipo")

        ax2 = self.figura.add_subplot(1, 2, 2)
        if por_zona:
            ax2.bar(
                [r["Zona"] for r in por_zona], [r["Total"] for r in por_zona],
                color=COLOR_ACENTO_SECUNDARIO, edgecolor=COLOR_ACENTO_SECUNDARIO, linewidth=0,
            )
        self._estilizar_eje(ax2, "Incidencias por zona")

        self.figura.tight_layout()
        self.canvas.draw()
