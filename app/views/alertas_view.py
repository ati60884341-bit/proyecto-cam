from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QCheckBox, QTextEdit, QMessageBox, QScrollArea,
)

from app.views.telegram_view import TelegramView
from app.views.UI.desplegable import Desplegable
from app.views.UI.iconos import pixmap_icono

COLORES_ESTADO = {
    "ok": ("#0f3d2e", "#36d6a0"),
    "aviso": ("#3d300f", "#f0c060"),
    "error": ("#3d1414", "#ff8a8a"),
}

AYUDA_DATOS_META = """<h3>Como conseguir los datos (una sola vez, gratis)</h3>
<ol>
<li>Entre a <b>developers.facebook.com</b> con su Facebook, cree una app de tipo
<b>Empresa (Business)</b> y agreguele el producto <b>WhatsApp</b>.</li>
<li>En <b>WhatsApp &gt; Configuracion de la API</b>, Meta le da un <b>numero de prueba gratis</b>.
Copie el <b>Identificador del numero de telefono</b> (Phone number ID).</li>
<li>En el campo <b>Para</b> agregue su celular y confirmelo con el codigo que le llega por WhatsApp.</li>
<li><b>Token permanente:</b> en <b>business.facebook.com &gt; Configuracion &gt; Usuarios del sistema</b>,
cree un usuario (Administrador), asignele la app y pulse <b>Generar token</b> con los permisos
<i>whatsapp_business_messaging</i> y <i>whatsapp_business_management</i>.
(El token temporal de la pagina de la API vence en 24 h: no sirve para la expo.)</li>
<li><b style="color:#ff8a8a;">No agregue tarjeta ni metodo de pago.</b> Asi Meta no puede cobrarle nada.</li>
</ol>"""


class AlertasView(QWidget):
    """Pestana "Alertas al celular": WhatsApp (principal) en 3 pasos y
    Telegram como respaldo automatico."""

    guardar_whatsapp_solicitado = pyqtSignal(dict)
    ventana_abierta_avisada = pyqtSignal()
    probar_whatsapp_solicitado = pyqtSignal()
    whatsapp_activo_cambiado = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        contenido = QWidget()
        scroll.setWidget(contenido)
        externo.addWidget(scroll)
        layout = QVBoxLayout(contenido)

        encabezado = QHBoxLayout()
        icono_titulo = QLabel()
        icono_titulo.setPixmap(pixmap_icono("telegram", "#36d6c9", 30))
        encabezado.addWidget(icono_titulo)
        titulos = QVBoxLayout()
        titulo = QLabel("Alertas al celular")
        titulo.setStyleSheet("font-size: 18px; font-weight: bold;")
        titulos.addWidget(titulo)
        subtitulo = QLabel(
            "Si tapan o mueven una camara, le llega al celular la foto de 3 segundos antes con su firma."
        )
        subtitulo.setStyleSheet("color: #9aa6b3;")
        titulos.addWidget(subtitulo)
        encabezado.addLayout(titulos, stretch=1)
        layout.addLayout(encabezado)

        # estado en una frase: lo primero que se lee
        self.lbl_estado = QLabel()
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        # ---- paso 1 ----
        paso1 = QGroupBox("Paso 1 · Conectar WhatsApp (una sola vez)")
        form = QFormLayout(paso1)
        self.campo_token = QLineEdit()
        self.campo_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_token.setPlaceholderText("Token permanente de Meta (EAA...)")
        form.addRow("Token:", self.campo_token)
        self.campo_phone_id = QLineEdit()
        self.campo_phone_id.setPlaceholderText("Identificador del numero de telefono, ej: 106540352242922")
        form.addRow("ID del numero:", self.campo_phone_id)
        self.campo_numero = QLineEdit()
        self.campo_numero.setPlaceholderText("Su celular con codigo de pais, ej: 51987654321")
        form.addRow("Su celular:", self.campo_numero)
        fila1 = QHBoxLayout()
        btn_ayuda = QPushButton("¿De donde saco estos datos?")
        btn_ayuda.clicked.connect(self._mostrar_ayuda)
        fila1.addWidget(btn_ayuda)
        btn_guardar = QPushButton("Guardar")
        btn_guardar.setStyleSheet("QPushButton { background: #1f8f86; font-weight: bold; }")
        btn_guardar.clicked.connect(self._emitir_guardar)
        fila1.addWidget(btn_guardar)
        form.addRow(fila1)
        layout.addWidget(paso1)

        # ---- paso 2 ----
        paso2 = QGroupBox("Paso 2 · Abrir la conversacion (cada 24 horas, ej. al empezar el turno)")
        v2 = QVBoxLayout(paso2)
        explicacion = QLabel(
            "Desde su WhatsApp, escribale \"inicio turno\" al numero del bot. Durante las 24 horas "
            "siguientes las alertas le llegan gratis. Despues pulse el boton:"
        )
        explicacion.setWordWrap(True)
        v2.addWidget(explicacion)
        fila2 = QHBoxLayout()
        self.btn_ya_escribi = QPushButton("Ya le escribi \"inicio turno\"")
        self.btn_ya_escribi.clicked.connect(self.ventana_abierta_avisada.emit)
        fila2.addWidget(self.btn_ya_escribi)
        self.lbl_ventana = QLabel()
        fila2.addWidget(self.lbl_ventana, stretch=1)
        v2.addLayout(fila2)
        layout.addWidget(paso2)

        # ---- paso 3 ----
        paso3 = QGroupBox("Paso 3 · Probar")
        v3 = QVBoxLayout(paso3)
        fila3 = QHBoxLayout()
        self.btn_probar = QPushButton("Enviar foto de prueba a WhatsApp")
        self.btn_probar.clicked.connect(self.probar_whatsapp_solicitado.emit)
        fila3.addWidget(self.btn_probar)
        self.lbl_prueba = QLabel()
        self.lbl_prueba.setWordWrap(True)
        fila3.addWidget(self.lbl_prueba, stretch=1)
        v3.addLayout(fila3)
        self.chk_activo = QCheckBox("Mandar las alertas por WhatsApp (si lo desmarca, van solo por Telegram)")
        self.chk_activo.toggled.connect(self.whatsapp_activo_cambiado.emit)
        v3.addWidget(self.chk_activo)
        layout.addWidget(paso3)

        self.telegram_view = TelegramView()
        layout.addWidget(Desplegable(
            "Telegram: respaldo automatico (si WhatsApp no esta disponible, la alerta va por aqui)",
            self.telegram_view,
        ))

        layout.addWidget(QLabel("Registro:"))
        self.texto_registro = QTextEdit()
        self.texto_registro.setReadOnly(True)
        self.texto_registro.setMaximumHeight(110)
        layout.addWidget(self.texto_registro)
        layout.addStretch(1)

    def _mostrar_ayuda(self):
        caja = QMessageBox(self)
        caja.setWindowTitle("Datos de WhatsApp")
        caja.setText(AYUDA_DATOS_META)
        caja.exec()

    def _emitir_guardar(self):
        self.guardar_whatsapp_solicitado.emit({
            "token": self.campo_token.text().strip(),
            "phone_id": self.campo_phone_id.text().strip(),
            "numero": self.campo_numero.text().strip(),
        })

    def cargar(self, cfg):
        self.campo_token.setText(cfg["token"])
        self.campo_phone_id.setText(cfg["phone_id"])
        self.campo_numero.setText(cfg["numero"])
        self.chk_activo.blockSignals(True)
        self.chk_activo.setChecked(cfg["activo"])
        self.chk_activo.blockSignals(False)

    def set_estado(self, tipo, texto):
        fondo, borde = COLORES_ESTADO[tipo]
        self.lbl_estado.setText(texto)
        self.lbl_estado.setStyleSheet(
            f"background: {fondo}; border: 1px solid {borde}; border-radius: 8px; padding: 10px;"
            f" font-size: 14px; font-weight: bold; color: {borde};"
        )

    def set_ventana(self, texto, abierta):
        self.lbl_ventana.setText(texto)
        self.lbl_ventana.setStyleSheet(f"color: {'#36d6a0' if abierta else '#f0c060'}; font-weight: bold;")

    def set_resultado_prueba(self, ok, texto):
        self.lbl_prueba.setText(texto)
        self.lbl_prueba.setStyleSheet(f"color: {'#36d6a0' if ok else '#ff8a8a'}; font-weight: bold;")

    def set_probando(self, activo):
        self.btn_probar.setEnabled(not activo)
        self.btn_probar.setText("Enviando..." if activo else "Enviar foto de prueba a WhatsApp")

    def registrar_evento(self, texto):
        self.texto_registro.append(texto)
