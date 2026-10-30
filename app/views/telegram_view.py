from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QTextEdit,
)


class TelegramView(QWidget):
    """Configuracion de alertas instantaneas a Telegram: cuando se detecta
    sabotaje o panico, la foto + firma SHA-256 se envian de inmediato al
    celular de quien este en el canal/chat configurado (ej. el jurado)."""

    guardar_solicitado = pyqtSignal(dict)
    probar_solicitado = pyqtSignal()
    generar_qr_solicitado = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Cuando el sistema detecta un sabotaje o activa el modo panico, envia de inmediato\n"
            "la foto de evidencia y su firma SHA-256 a este chat/canal de Telegram — ideal para\n"
            "que el jurado reciba la alerta en su propio celular durante la demo en vivo."
        )
        layout.addWidget(intro)

        grupo_config = QGroupBox("Configuracion del bot")
        formulario = QFormLayout(grupo_config)

        self.campo_token = QLineEdit()
        self.campo_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_token.setPlaceholderText("Token de @BotFather, ej: 123456789:AAH...")
        formulario.addRow("Bot Token:", self.campo_token)

        self.campo_chat_id = QLineEdit()
        self.campo_chat_id.setPlaceholderText("Chat ID o Channel ID, ej: -1001234567890")
        formulario.addRow("Chat ID:", self.campo_chat_id)

        self.campo_username = QLineEdit()
        self.campo_username.setPlaceholderText("usuario del bot (sin @), ej: CentinelaFeriaBot")
        formulario.addRow("Usuario del bot (para el QR):", self.campo_username)

        fila_botones = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar configuracion")
        self.btn_guardar.clicked.connect(self._emitir_guardar)
        fila_botones.addWidget(self.btn_guardar)

        self.btn_probar = QPushButton("Enviar mensaje de prueba")
        self.btn_probar.clicked.connect(self.probar_solicitado.emit)
        fila_botones.addWidget(self.btn_probar)
        formulario.addRow(fila_botones)

        layout.addWidget(grupo_config)

        grupo_qr = QGroupBox("Codigo QR para que el jurado se una")
        qr_layout = QVBoxLayout(grupo_qr)
        self.btn_generar_qr = QPushButton("Generar QR")
        self.btn_generar_qr.clicked.connect(
            lambda: self.generar_qr_solicitado.emit(self.campo_username.text().strip())
        )
        qr_layout.addWidget(self.btn_generar_qr)

        self.lbl_qr = QLabel("Guarde el usuario del bot arriba y pulse \"Generar QR\".")
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr.setMinimumHeight(260)
        self.lbl_qr.setStyleSheet("background: white; color: #333;")
        qr_layout.addWidget(self.lbl_qr)

        self.lbl_link_qr = QLabel("")
        self.lbl_link_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_layout.addWidget(self.lbl_link_qr)

        layout.addWidget(grupo_qr)

        grupo_estado = QGroupBox("Estado")
        estado_layout = QVBoxLayout(grupo_estado)
        self.texto_estado = QTextEdit()
        self.texto_estado.setReadOnly(True)
        self.texto_estado.setMaximumHeight(120)
        estado_layout.addWidget(self.texto_estado)
        layout.addWidget(grupo_estado)

    def _emitir_guardar(self):
        self.guardar_solicitado.emit({
            "bot_token": self.campo_token.text().strip(),
            "chat_id": self.campo_chat_id.text().strip(),
            "bot_username": self.campo_username.text().strip(),
        })

    def cargar_config(self, cfg):
        self.campo_token.setText(cfg.get("bot_token", ""))
        self.campo_chat_id.setText(cfg.get("chat_id", ""))
        self.campo_username.setText(cfg.get("bot_username", ""))

    def mostrar_qr(self, imagen_png_bytes, link):
        pixmap = QPixmap()
        pixmap.loadFromData(imagen_png_bytes)
        self.lbl_qr.setPixmap(pixmap.scaled(
            240, 240, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        ))
        self.lbl_link_qr.setText(link)

    def registrar_evento(self, texto):
        self.texto_estado.append(texto)
