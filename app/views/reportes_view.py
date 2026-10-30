from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


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

        self.figura = Figure(figsize=(8, 5))
        self.canvas = FigureCanvasQTAgg(self.figura)
        layout.addWidget(self.canvas)

    def actualizar_graficos(self, por_tipo, por_zona):
        self.figura.clear()

        ax1 = self.figura.add_subplot(1, 2, 1)
        if por_tipo:
            ax1.bar([r["Tipo"] for r in por_tipo], [r["Total"] for r in por_tipo], color="#3a7bd5")
        ax1.set_title("Incidencias por tipo")
        ax1.tick_params(axis="x", rotation=30)

        ax2 = self.figura.add_subplot(1, 2, 2)
        if por_zona:
            ax2.bar([r["Zona"] for r in por_zona], [r["Total"] for r in por_zona], color="#d53a3a")
        ax2.set_title("Incidencias por zona")
        ax2.tick_params(axis="x", rotation=30)

        self.figura.tight_layout()
        self.canvas.draw()
