"""Seccion que se abre/cierra con un clic: esconde los campos que casi
nadie toca (puerto, canal, perfiles...) para que el formulario se vea corto."""
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

ESTILO_TITULO = (
    "QPushButton { background: transparent; border: none; color: #7fd6e8; text-align: left; padding: 4px 0; }"
    "QPushButton:hover { color: #36d6c9; }"
)


class Desplegable(QWidget):
    def __init__(self, titulo, contenido, abierto=False, parent=None):
        super().__init__(parent)
        self._titulo = titulo
        self.contenido = contenido
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.boton = QPushButton()
        self.boton.setStyleSheet(ESTILO_TITULO)
        self.boton.clicked.connect(lambda: self.set_abierto(not self.contenido.isVisible()))
        layout.addWidget(self.boton)
        layout.addWidget(contenido)
        self.set_abierto(abierto)

    def set_abierto(self, abierto):
        self.contenido.setVisible(abierto)
        self.boton.setText(("▾  " if abierto else "▸  ") + self._titulo)
