from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QLineEdit, QPushButton, QLabel, QMessageBox,
)

from app.views.UI.fondo_nocturno import FondoNocturno
from app.views.UI.pantalla import tamano_adaptado

_ESTILO_TARJETA = """
#tarjetaLogin {
    background: rgba(14, 17, 24, 195);
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 18px;
}
QLabel#tituloLogin { color: #ffffff; font-size: 16px; font-weight: 600; }
QLabel#subtituloLogin, QLabel#ayudaLogin { color: #9aa0ac; font-size: 11px; }
QLabel[class="etiquetaCampo"] { color: #9aa0ac; font-size: 11.5px; }
QLineEdit {
    background: #12151d; border: 1px solid #2a303c; border-radius: 9px;
    padding: 9px 11px; color: #e7e9ee; font-size: 13px;
}
QLineEdit:focus { border: 1px solid #36d6c9; }
QPushButton#btnIngresar {
    background: #36d6c9; color: #06201d; border: none; border-radius: 9px;
    padding: 10px; font-weight: 600; font-size: 13.5px;
}
QPushButton#btnIngresar:hover { background: #4fe4d8; }
"""


class LoginView(QWidget):
    intento_login = pyqtSignal(str, str)  # usuario, clave

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAM - Centro de Monitoreo Inteligente")
        # ancha (panoramica), no angosta: la escena es un paisaje horizontal
        # (como la foto de referencia) - una ventana angosta y alta la
        # obligaba a recortar casi todo menos una tira vertical del medio
        self.resize(*tamano_adaptado(860, 540))

        fondo = FondoNocturno(self, animado=True, opacidad_superposicion=0.35)
        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.addWidget(fondo)

        layout_fondo = QVBoxLayout(fondo)
        layout_fondo.addStretch(1)

        tarjeta = QFrame()
        tarjeta.setObjectName("tarjetaLogin")
        tarjeta.setFixedWidth(320)
        tarjeta.setStyleSheet(_ESTILO_TARJETA)
        layout_tarjeta = QVBoxLayout(tarjeta)
        layout_tarjeta.setContentsMargins(26, 28, 26, 24)
        layout_tarjeta.setSpacing(4)

        titulo = QLabel("Sistema inteligente de\nvideovigilancia")
        titulo.setObjectName("tituloLogin")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_tarjeta.addWidget(titulo)

        subtitulo = QLabel("Ingresa con tu cuenta para continuar")
        subtitulo.setObjectName("subtituloLogin")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_tarjeta.addWidget(subtitulo)
        layout_tarjeta.addSpacing(18)

        etiqueta_usuario = QLabel("Usuario")
        etiqueta_usuario.setProperty("class", "etiquetaCampo")
        layout_tarjeta.addWidget(etiqueta_usuario)
        self.campo_usuario = QLineEdit()
        self.campo_usuario.setPlaceholderText("admin / vigilante")
        layout_tarjeta.addWidget(self.campo_usuario)
        layout_tarjeta.addSpacing(10)

        etiqueta_clave = QLabel("Contraseña")
        etiqueta_clave.setProperty("class", "etiquetaCampo")
        layout_tarjeta.addWidget(etiqueta_clave)
        self.campo_clave = QLineEdit()
        self.campo_clave.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_clave.setPlaceholderText("123456")
        layout_tarjeta.addWidget(self.campo_clave)
        layout_tarjeta.addSpacing(16)

        self.btn_ingresar = QPushButton("Ingresar")
        self.btn_ingresar.setObjectName("btnIngresar")
        self.btn_ingresar.clicked.connect(self._emitir_login)
        layout_tarjeta.addWidget(self.btn_ingresar)

        self.campo_clave.returnPressed.connect(self._emitir_login)

        ayuda = QLabel("Usuarios demo: admin / 123456  —  vigilante / 123456")
        ayuda.setObjectName("ayudaLogin")
        ayuda.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ayuda.setWordWrap(True)
        layout_tarjeta.addSpacing(14)
        layout_tarjeta.addWidget(ayuda)

        fila_tarjeta = QVBoxLayout()
        fila_tarjeta.addWidget(tarjeta, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout_fondo.addLayout(fila_tarjeta)
        layout_fondo.addStretch(1)

    def _emitir_login(self):
        self.intento_login.emit(self.campo_usuario.text().strip(), self.campo_clave.text())

    def mostrar_error(self, mensaje):
        QMessageBox.warning(self, "No se pudo iniciar sesion", mensaje)
