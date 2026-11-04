from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

from app.views.UI.zona_frame import frame_a_pixmap
from app.views.UI.pantalla import tamano_adaptado


class ZonaAmpliadaDialog(QDialog):
    """Vista en 'pantalla completa' de una zona (comando de voz: 'sistema ampliar <zona>')."""

    def __init__(self, nombre_zona, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Zona ampliada: {nombre_zona}")
        self.resize(*tamano_adaptado(900, 650))
        layout = QVBoxLayout(self)
        self.video_label = QLabel("Cargando video...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background: black; color: white;")
        layout.addWidget(self.video_label)

    def mostrar_frame(self, frame_bgr):
        pixmap = frame_a_pixmap(frame_bgr, self.video_label.width(), self.video_label.height())
        self.video_label.setPixmap(pixmap)
