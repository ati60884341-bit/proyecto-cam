import os
import webbrowser

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit, QPushButton, QApplication,
)

from app.config import MANUALES_DIR

# (titulo, archivo local, descripcion, enlace para compartir/editar)
# el enlace compartible es el mismo manual publicado como pagina web: sirve
# para mandarselo a alguien que aun no tiene el programa instalado, o para
# pedirle ayuda a Claude a editarlo (ej. agregar el usuario/clave real de
# una camara a los ejemplos) sin tocar el archivo local directamente.
MANUALES = [
    (
        "Conectar tus cámaras",
        "conectar_camaras.html",
        "Cómo agregar una cámara IP/WiFi, un DVR/NVR completo o una webcam USB, paso a paso.",
        "https://claude.ai/artifact/XALKWiKoSKN5YDmaxLsF4d",
    ),
    (
        "Comandos de voz",
        "comandos_voz.html",
        "Cómo activar el micrófono y qué decir para controlar el sistema sin tocar el mouse.",
        "https://claude.ai/artifact/WiXGh9H6tgoVGRKTSCyvr3",
    ),
    (
        "Conectar la cámara, el DVR y la red",
        "conectar_red_dvr.html",
        "Qué cable va en cada puerto del DVR, y cómo dejarlo en la misma red que la PC antes de abrir el programa.",
        "https://claude.ai/artifact/Aq4NLfxMrMbk5rn13BEyoj",
    ),
]


class ManualesView(QWidget):
    """Pestana "Manuales": abre las guias ilustradas (vienen con el programa,
    funcionan sin internet) y deja copiar el enlace de la version web de
    cada una, por si hay que compartirla o pedir que se edite."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Guías paso a paso para quien recién usa el programa. Se abren en el navegador\n"
            "y funcionan sin conexión a internet (están guardadas dentro del programa)."
        )
        layout.addWidget(intro)

        for titulo, archivo, descripcion, enlace in MANUALES:
            grupo = QGroupBox(titulo)
            v = QVBoxLayout(grupo)
            v.addWidget(QLabel(descripcion))

            fila_botones = QHBoxLayout()
            btn_abrir = QPushButton("Abrir manual")
            btn_abrir.clicked.connect(lambda _checked, a=archivo: self._abrir_manual(a))
            fila_botones.addWidget(btn_abrir)
            fila_botones.addStretch()
            v.addLayout(fila_botones)

            v.addWidget(QLabel("Enlace para compartir o editar:"))
            fila_enlace = QHBoxLayout()
            campo_enlace = QLineEdit(enlace)
            campo_enlace.setReadOnly(True)
            fila_enlace.addWidget(campo_enlace)
            btn_copiar = QPushButton("Copiar enlace")
            btn_copiar.clicked.connect(lambda _checked, e=enlace, b=None: self._copiar_enlace(e, btn_copiar))
            fila_enlace.addWidget(btn_copiar)
            v.addLayout(fila_enlace)

            layout.addWidget(grupo)

        layout.addStretch()

    def _abrir_manual(self, archivo):
        ruta = os.path.join(MANUALES_DIR, archivo)
        webbrowser.open(f"file:///{ruta}")

    def _copiar_enlace(self, enlace, boton):
        QApplication.clipboard().setText(enlace)
        texto_original = boton.text()
        boton.setText("¡Copiado!")

        def restaurar():
            boton.setText(texto_original)

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, restaurar)
