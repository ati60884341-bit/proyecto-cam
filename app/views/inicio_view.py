"""Pantalla de Inicio: lo primero que se ve al entrar. Un respiro antes del
monitoreo, con la escena nocturna animada de fondo, un saludo y mensajes
que acompanan al vigilante (para que no sienta que esta solo en el turno)."""
import time

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.views.UI.fondo_nocturno import FondoNocturno

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

ESTILO_TARJETA = (
    "QFrame, QWidget#tarjetaInicio { background: rgba(14, 20, 30, 170); border: 1px solid rgba(127, 214, 232, 60);"
    " border-radius: 14px; }"
)
COLOR_ESTADO = {"ok": "#36d6a0", "aviso": "#f0c060", "error": "#ff8a8a"}


def saludo_por_hora(hora):
    if hora < 12:
        return "Buenos dias"
    if hora < 19:
        return "Buenas tardes"
    return "Buenas noches"


def mensajes_de_compania(total_camaras):
    primero = (
        f"Hoy tienes {total_camaras} camara{'s' if total_camaras != 1 else ''} cuidando el lugar contigo."
        if total_camaras else "Todavia no hay camaras: agregalas en la pestana \"Camaras\" o \"NVR / DVR\"."
    )
    return [
        primero,
        "Respira tranquilo: si alguien tapa una camara, la alarma te avisa al instante.",
        "Tomate un cafe. Yo sigo vigilando mientras tanto.",
        "No estas solo en este turno: el sistema te acompana.",
        "Cada foto de evidencia queda firmada: nadie puede alterarla.",
        "Al empezar el turno, escribele \"inicio turno\" al bot de WhatsApp.",
        "¿Necesitas ver una camara rapido? Manten el microfono y di \"camara 1 ampliar\".",
    ]


class _Tarjeta(QWidget):
    def __init__(self, titulo):
        super().__init__()
        self.setObjectName("tarjetaInicio")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(ESTILO_TARJETA)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 14)
        etiqueta = QLabel(titulo)
        etiqueta.setStyleSheet("color: #9aa6b3; font-size: 12px; background: transparent; border: none;")
        v.addWidget(etiqueta)
        self.valor = QLabel("...")
        self.valor.setWordWrap(True)
        self.valor.setStyleSheet("color: #e7e9ee; font-size: 20px; font-weight: bold; background: transparent; border: none;")
        v.addWidget(self.valor)

    def set_valor(self, texto, color="#e7e9ee", tamano=20):
        self.valor.setText(texto)
        self.valor.setStyleSheet(
            f"color: {color}; font-size: {tamano}px; font-weight: bold; background: transparent; border: none;"
        )


class InicioView(FondoNocturno):
    ir_a_monitoreo = pyqtSignal()

    INTERVALO_MENSAJE_MS = 7000

    def __init__(self, usuario, parent=None):
        super().__init__(parent, animado=True, opacidad_superposicion=0.45)
        self._nombre = usuario.get("NombreCompleto") or "vigilante"
        self._mensajes = mensajes_de_compania(0)
        self._indice_mensaje = 0

        externo = QVBoxLayout(self)
        externo.setContentsMargins(40, 30, 40, 40)
        externo.addStretch(2)

        self.lbl_fecha = QLabel()
        self.lbl_fecha.setStyleSheet(
            "color: #7fd6e8; font-size: 13px; background: rgba(14, 20, 30, 150);"
            " border: 1px solid rgba(127, 214, 232, 70); border-radius: 12px; padding: 5px 14px;"
        )
        externo.addWidget(self.lbl_fecha, alignment=Qt.AlignmentFlag.AlignHCenter)
        externo.addSpacing(16)

        self.lbl_saludo = QLabel()
        self.lbl_saludo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_saludo.setWordWrap(True)
        self.lbl_saludo.setStyleSheet("color: white; font-size: 34px; font-weight: bold; background: transparent;")
        externo.addWidget(self.lbl_saludo)

        self.lbl_mensaje = QLabel()
        self.lbl_mensaje.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mensaje.setWordWrap(True)
        self.lbl_mensaje.setMinimumHeight(48)
        self.lbl_mensaje.setStyleSheet("color: #cfe9ef; font-size: 17px; background: transparent;")
        self._opacidad = QGraphicsOpacityEffect(self.lbl_mensaje)
        self.lbl_mensaje.setGraphicsEffect(self._opacidad)
        externo.addWidget(self.lbl_mensaje)
        externo.addSpacing(28)

        fila = QHBoxLayout()
        fila.setSpacing(16)
        self.tarjeta_camaras = _Tarjeta("Camaras en linea")
        self.tarjeta_incidencias = _Tarjeta("Incidencias de hoy")
        self.tarjeta_alertas = _Tarjeta("Alertas al celular")
        for tarjeta in (self.tarjeta_camaras, self.tarjeta_incidencias, self.tarjeta_alertas):
            tarjeta.setMaximumWidth(320)
            fila.addWidget(tarjeta)
        contenedor = QWidget()
        contenedor.setStyleSheet("background: transparent;")
        contenedor.setLayout(fila)
        contenedor.setMaximumWidth(1000)
        externo.addWidget(contenedor, alignment=Qt.AlignmentFlag.AlignHCenter)
        externo.addSpacing(28)

        self.btn_entrar = QPushButton("Ir al Centro de Monitoreo")
        self.btn_entrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_entrar.setStyleSheet(
            "QPushButton { background: #1f8f86; color: white; font-size: 16px; font-weight: bold;"
            " padding: 14px 34px; border-radius: 12px; border: none; }"
            "QPushButton:hover { background: #26a89e; }"
        )
        self.btn_entrar.clicked.connect(self.ir_a_monitoreo.emit)
        externo.addWidget(self.btn_entrar, alignment=Qt.AlignmentFlag.AlignHCenter)
        externo.addStretch(3)

        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._actualizar_reloj)
        self._reloj.start(1000)
        self._rotador = QTimer(self)
        self._rotador.timeout.connect(self._siguiente_mensaje)
        self._actualizar_reloj()
        self._mostrar_mensaje()

    # ---------------- reloj y saludo ----------------
    def _actualizar_reloj(self):
        ahora = time.localtime()
        self.lbl_fecha.setText(
            f"{DIAS[ahora.tm_wday].capitalize()} {ahora.tm_mday} de {MESES[ahora.tm_mon - 1]}  ·  {time.strftime('%H:%M', ahora)}"
        )
        self.lbl_saludo.setText(f"{saludo_por_hora(ahora.tm_hour)}, {self._nombre}")

    # ---------------- mensajes que van cambiando ----------------
    def set_mensajes(self, mensajes):
        self._mensajes = mensajes
        self.lbl_mensaje.setText(mensajes[self._indice_mensaje % len(mensajes)])

    def _mostrar_mensaje(self):
        self.lbl_mensaje.setText(self._mensajes[self._indice_mensaje % len(self._mensajes)])
        animacion = QPropertyAnimation(self._opacidad, b"opacity", self)
        animacion.setDuration(700)
        animacion.setStartValue(0.0)
        animacion.setEndValue(1.0)
        animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
        animacion.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _siguiente_mensaje(self):
        self._indice_mensaje += 1
        self._mostrar_mensaje()

    # solo se anima mientras se ve: en el monitoreo no gasta nada
    def showEvent(self, event):
        super().showEvent(event)
        self._rotador.start(self.INTERVALO_MENSAJE_MS)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._rotador.stop()

    # ---------------- resumen ----------------
    def set_resumen(self, en_linea, total, incidencias_hoy, tipo_alertas, texto_alertas):
        color = "#36d6a0" if total and en_linea == total else ("#f0c060" if en_linea else "#ff8a8a")
        self.tarjeta_camaras.set_valor(f"{en_linea} de {total}", color)
        self.tarjeta_incidencias.set_valor(str(incidencias_hoy))
        self.tarjeta_alertas.set_valor(texto_alertas, COLOR_ESTADO[tipo_alertas], 13)
