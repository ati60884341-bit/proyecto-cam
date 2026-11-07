from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QApplication

from app.views.UI.fondo_nocturno import FondoNocturno
from app.views.UI.pantalla import tamano_adaptado

_ESTILO_BARRA = """
QProgressBar { background: rgba(255,255,255,40); border: none; border-radius: 2px; }
QProgressBar::chunk { background: #36d6c9; border-radius: 2px; }
"""


class SplashView(QWidget):
    """Pantalla de carga animada que se muestra unos segundos al abrir el
    programa, antes del login: misma escena nocturna de FondoNocturno
    (aqui ANIMADA) para que la identidad visual del programa se sienta
    desde el primer instante, no solo despues de iniciar sesion."""

    terminado = pyqtSignal()

    def __init__(self, duracion_ms=2200, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.resize(*tamano_adaptado(640, 400))
        self._centrar_en_pantalla()

        fondo = FondoNocturno(self, animado=True, opacidad_superposicion=0.25)
        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.addWidget(fondo)

        layout_fondo = QVBoxLayout(fondo)
        layout_fondo.setContentsMargins(0, 70, 0, 40)
        layout_fondo.addStretch(1)

        titulo = QLabel(
            '<span style="color:#ffffff;">C</span>'
            '<span style="color:#36d6c9;">A</span>'
            '<span style="color:#ffffff;">M</span>'
        )
        titulo.setTextFormat(Qt.TextFormat.RichText)
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titulo.setStyleSheet("font-size: 42px; font-weight: 700; letter-spacing: 6px;")
        layout_fondo.addWidget(titulo)

        subtitulo = QLabel("Sistema inteligente de videovigilancia y auditoría")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitulo.setStyleSheet("color: #9aa0ac; font-size: 12px;")
        layout_fondo.addWidget(subtitulo)
        layout_fondo.addSpacing(26)

        barra = QProgressBar()
        barra.setRange(0, 0)  # indeterminado: no sabemos cuanto tarda la carga real
        barra.setFixedSize(220, 4)
        barra.setTextVisible(False)
        barra.setStyleSheet(_ESTILO_BARRA)
        fila_barra = QHBoxLayout()
        fila_barra.addStretch(1)
        fila_barra.addWidget(barra)
        fila_barra.addStretch(1)
        layout_fondo.addLayout(fila_barra)

        layout_fondo.addStretch(2)

        QTimer.singleShot(duracion_ms, self.terminado.emit)

    def _centrar_en_pantalla(self):
        pantalla = QApplication.primaryScreen()
        if pantalla is None:
            return
        geometria = pantalla.availableGeometry()
        x = geometria.x() + (geometria.width() - self.width()) // 2
        y = geometria.y() + (geometria.height() - self.height()) // 2
        self.move(x, y)
