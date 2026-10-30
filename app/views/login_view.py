from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QMessageBox,
)


class LoginView(QWidget):
    intento_login = pyqtSignal(str, str)  # usuario, clave

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAM - Centro de Monitoreo Inteligente")
        self.resize(420, 260)

        layout = QVBoxLayout(self)

        titulo = QLabel("Sistema Inteligente de Videovigilancia (CAM)")
        titulo.setStyleSheet("font-size: 16px; font-weight: bold;")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titulo)

        subtitulo = QLabel("Ingrese sus credenciales para acceder al centro de monitoreo")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitulo)

        formulario = QFormLayout()
        self.campo_usuario = QLineEdit()
        self.campo_usuario.setPlaceholderText("admin / vigilante")
        self.campo_clave = QLineEdit()
        self.campo_clave.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_clave.setPlaceholderText("123456")
        formulario.addRow("Usuario:", self.campo_usuario)
        formulario.addRow("Clave:", self.campo_clave)
        layout.addLayout(formulario)

        self.btn_ingresar = QPushButton("Ingresar")
        self.btn_ingresar.clicked.connect(self._emitir_login)
        layout.addWidget(self.btn_ingresar)

        self.campo_clave.returnPressed.connect(self._emitir_login)

        ayuda = QLabel("Usuarios demo: admin / 123456  —  vigilante / 123456")
        ayuda.setStyleSheet("color: gray; font-size: 10px;")
        ayuda.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ayuda)

    def _emitir_login(self):
        self.intento_login.emit(self.campo_usuario.text().strip(), self.campo_clave.text())

    def mostrar_error(self, mensaje):
        QMessageBox.warning(self, "No se pudo iniciar sesion", mensaje)
