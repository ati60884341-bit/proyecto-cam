from PyQt6.QtCore import Qt, QRect, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QPushButton, QLabel, QStackedWidget,
    QGraphicsOpacityEffect,
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
from app.views.UI.fondo_nocturno import FondoNocturno
from app.views.UI.iconos import icono

_COLOR_ICONO_INACTIVO = "#9aa6b3"
_COLOR_ICONO_ACTIVO = "#36d6c9"

_ESTILO_NAV = """
QPushButton#navBoton {
    color: #c7cdd6; background: transparent; border: none;
    padding: 10px 12px; text-align: left; font-size: 13px; border-radius: 8px;
    margin: 1px 8px;
}
QPushButton#navBoton:hover { background: rgba(255, 255, 255, 20); color: #ffffff; }
QPushButton#navBoton[activo="true"] {
    background: rgba(54, 214, 201, 30); color: #ffffff; font-weight: 600;
}
QPushButton#btnSalir {
    color: #ffd9d6; background: rgba(192, 57, 43, 60); border: 1px solid rgba(192, 57, 43, 140);
    border-radius: 9px; padding: 10px; font-weight: 600;
}
QPushButton#btnSalir:hover { background: rgba(192, 57, 43, 100); }
"""


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
        # misma escena nocturna animada del splash/login (el GIF real, no
        # una recreacion) - se probo primero quieta aca por cuidar CPU/GPU
        # frente a los hilos de video de cada camara en vivo, pero el GIF es
        # chico (720x364) y decodificarlo de fondo no compite de verdad con
        # eso; si en el futuro se nota mas lento con varias camaras a la
        # vez, el primer sospechoso es esta linea (volver a animado=False).
        # overlay 0.4: a mas oscuro, mas "aplastaba" el detalle de la imagen
        # (colinas/arbol) hasta verse borroso en vez de nitido
        barra = FondoNocturno(animado=True, opacidad_superposicion=0.4)
        barra.setObjectName("barraLateral")
        barra.setFixedWidth(210)
        barra.setStyleSheet(_ESTILO_NAV)
        layout_barra = QVBoxLayout(barra)
        layout_barra.setContentsMargins(0, 14, 0, 14)
        layout_barra.setSpacing(2)

        lbl_usuario = QLabel(f"{usuario['NombreCompleto']}\n({usuario['Rol']})")
        lbl_usuario.setStyleSheet("color: white; font-weight: bold; padding: 0 14px 14px;")
        layout_barra.addWidget(lbl_usuario)

        # indicador de seccion activa: una barrita angosta que se DESLIZA
        # (QPropertyAnimation) hasta el boton elegido en vez de aparecer de
        # golpe - ver _mover_indicador
        self.indicador_activo = QFrame(barra)
        self.indicador_activo.setStyleSheet("background: #36d6c9; border-radius: 2px;")
        self.indicador_activo.hide()

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
            boton.setObjectName("navBoton")
            boton.setProperty("activo", "false")
            boton.setIcon(icono(clave, color=_COLOR_ICONO_INACTIVO, tamano=18))
            boton.setIconSize(QSize(18, 18))
            boton.clicked.connect(lambda _checked, k=clave: self.mostrar_seccion(k))
            layout_barra.addWidget(boton)
            self.botones[clave] = boton

        layout_barra.addStretch()
        self.btn_salir = QPushButton("Cerrar sesion")
        self.btn_salir.setObjectName("btnSalir")
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

        self._seccion_actual = None
        self._animacion_indicador = None
        self._animacion_fade = None
        self.mostrar_seccion("dashboard")
        # al construirse, los botones del sidebar todavia no tienen una
        # geometria real (no hubo layout ni se mostro la ventana): se ubica
        # el indicador una vez que el bucle de eventos ya hizo ese primer
        # layout, sin animacion (es la posicion inicial, no una transicion)
        QTimer.singleShot(0, lambda: self._mover_indicador(animado=False))

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
        self._seccion_actual = clave

        for k, boton in self.botones.items():
            activo = k == clave
            boton.setProperty("activo", "true" if activo else "false")
            boton.style().unpolish(boton)
            boton.style().polish(boton)
            boton.setIcon(icono(k, color=(_COLOR_ICONO_ACTIVO if activo else _COLOR_ICONO_INACTIVO), tamano=18))

        self._mover_indicador(animado=True)
        self._iniciar_fade_contenido()

    def _mover_indicador(self, animado=True):
        boton = self.botones.get(self._seccion_actual)
        if boton is None or boton.height() <= 0:
            return  # todavia no hay layout real (ver el singleShot en __init__)
        destino = QRect(0, boton.y() + 6, 3, boton.height() - 12)
        if not animado or not self.indicador_activo.isVisible():
            self.indicador_activo.setGeometry(destino)
            self.indicador_activo.show()
            return
        animacion = QPropertyAnimation(self.indicador_activo, b"geometry", self.indicador_activo)
        animacion.setDuration(220)
        animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
        animacion.setStartValue(self.indicador_activo.geometry())
        animacion.setEndValue(destino)
        animacion.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._animacion_indicador = animacion

    def _iniciar_fade_contenido(self):
        """Pequeno fundido (180ms) al cambiar de pestana - el efecto se
        retira apenas termina (DeleteWhenStopped + quitar el graphics
        effect) para no dejarlo puesto sobre el Centro de Monitoreo, donde
        las camaras en vivo ya repintan varias veces por segundo y no les
        conviene pasar encima por un QGraphicsOpacityEffect permanente."""
        efecto = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(efecto)
        animacion = QPropertyAnimation(efecto, b"opacity", self.stack)
        animacion.setDuration(180)
        animacion.setStartValue(0.0)
        animacion.setEndValue(1.0)
        animacion.finished.connect(lambda: self.stack.setGraphicsEffect(None))
        animacion.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._animacion_fade = animacion
