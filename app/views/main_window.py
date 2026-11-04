from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QPushButton, QLabel, QStackedWidget,
)

from app.views.dashboard_view import DashboardView
from app.views.incidencias_view import IncidenciasView
from app.views.evidencias_view import EvidenciasView
from app.views.turnos_view import TurnosView
from app.views.reportes_view import ReportesView
from app.views.camaras_view import CamarasView
from app.views.dvr_view import DvrView
from app.views.radar_view import RadarView
from app.views.telegram_view import TelegramView
from app.views.manuales_view import ManualesView
from app.views.UI.pantalla import tamano_adaptado


class MainWindow(QMainWindow):
    """Ventana principal: barra lateral (QFrame) de navegacion + contenido
    en un QStackedWidget, tal como especifica la propuesta del proyecto."""

    def __init__(self, usuario, camaras, parent=None):
        super().__init__(parent)
        self.usuario = usuario
        self.setWindowTitle("CAM - Centro de Monitoreo Inteligente")
        # 1280x800 es el tamano ideal, pero en una laptop con pantalla chica
        # (ej. 1366x768, muy comun) se ajusta para que entre completa
        self.resize(*tamano_adaptado(1280, 800))

        contenedor = QWidget()
        self.setCentralWidget(contenedor)
        layout_raiz = QHBoxLayout(contenedor)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        # -------- barra lateral --------
        barra = QFrame()
        barra.setObjectName("barraLateral")
        barra.setFixedWidth(210)
        barra.setStyleSheet("#barraLateral { background: #1c2128; }")
        layout_barra = QVBoxLayout(barra)

        lbl_usuario = QLabel(f"{usuario['NombreCompleto']}\n({usuario['Rol']})")
        lbl_usuario.setStyleSheet("color: white; font-weight: bold; padding: 10px;")
        layout_barra.addWidget(lbl_usuario)

        self.botones = {}
        for clave, texto in [
            ("dashboard", "Centro de monitoreo"),
            ("incidencias", "Incidencias"),
            ("evidencias", "Evidencias"),
            ("turnos", "Turnos"),
            ("radar", "Radar de camaras"),
            ("camaras", "Camaras"),
            ("dvr", "NVR / DVR"),
            ("telegram", "Alertas Telegram"),
            ("reportes", "Reportes"),
            ("manuales", "Manuales"),
        ]:
            boton = QPushButton(texto)
            boton.setStyleSheet(
                "QPushButton { color: white; background: #262c36; border: none; padding: 12px; text-align: left; }"
                "QPushButton:hover { background: #333a46; }"
            )
            boton.clicked.connect(lambda _checked, k=clave: self.mostrar_seccion(k))
            layout_barra.addWidget(boton)
            self.botones[clave] = boton

        layout_barra.addStretch()
        self.btn_salir = QPushButton("Cerrar sesion")
        self.btn_salir.setStyleSheet("color: white; background: #7a1f1f; border: none; padding: 12px;")
        layout_barra.addWidget(self.btn_salir)

        layout_raiz.addWidget(barra)

        # -------- contenido (QStackedWidget) --------
        self.stack = QStackedWidget()
        self.dashboard_view = DashboardView(camaras)
        self.incidencias_view = IncidenciasView()
        self.evidencias_view = EvidenciasView()
        self.turnos_view = TurnosView()
        self.radar_view = RadarView()
        self.camaras_view = CamarasView()
        self.dvr_view = DvrView()
        self.telegram_view = TelegramView()
        self.reportes_view = ReportesView()
        self.manuales_view = ManualesView()

        for clave, vista in [
            ("dashboard", self.dashboard_view),
            ("incidencias", self.incidencias_view),
            ("evidencias", self.evidencias_view),
            ("turnos", self.turnos_view),
            ("radar", self.radar_view),
            ("camaras", self.camaras_view),
            ("dvr", self.dvr_view),
            ("telegram", self.telegram_view),
            ("reportes", self.reportes_view),
            ("manuales", self.manuales_view),
        ]:
            self.stack.addWidget(vista)

        layout_raiz.addWidget(self.stack, stretch=1)

        self.mostrar_seccion("dashboard")

    def mostrar_seccion(self, clave):
        vistas = {
            "dashboard": self.dashboard_view,
            "incidencias": self.incidencias_view,
            "evidencias": self.evidencias_view,
            "turnos": self.turnos_view,
            "radar": self.radar_view,
            "camaras": self.camaras_view,
            "dvr": self.dvr_view,
            "telegram": self.telegram_view,
            "reportes": self.reportes_view,
            "manuales": self.manuales_view,
        }
        self.stack.setCurrentWidget(vistas[clave])
