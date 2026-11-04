from app.models import camara_model
from app.views.main_window import MainWindow
from app.controllers.monitoreo_controller import MonitoreoController
from app.controllers.incidencia_controller import IncidenciaController
from app.controllers.evidencia_controller import EvidenciaController
from app.controllers.turno_controller import TurnoController
from app.controllers.reporte_controller import ReporteController
from app.controllers.camara_controller import CamaraController
from app.controllers.dvr_controller import DvrController
from app.controllers.telegram_controller import TelegramController


class AppController:
    """Arma la ventana principal y conecta cada vista con su controlador,
    siguiendo el patron MVC: Modelo (app.models) - Vista (app.views) -
    Controlador (app.controllers)."""

    def __init__(self, usuario):
        self.usuario = usuario
        camaras = camara_model.listar()

        self.main_window = MainWindow(usuario, camaras)

        self.turno_controller = TurnoController(self.main_window.turnos_view, usuario)
        self.incidencia_controller = IncidenciaController(self.main_window.incidencias_view)
        self.evidencia_controller = EvidenciaController(self.main_window.evidencias_view, usuario)
        self.reporte_controller = ReporteController(self.main_window.reportes_view)
        self.monitoreo_controller = MonitoreoController(
            self.main_window.dashboard_view, usuario, camaras,
            obtener_turno_actual=lambda: self.turno_controller.id_turno_actual,
        )
        self.camara_controller = CamaraController(
            self.main_window.camaras_view, usuario,
            on_camara_agregada=self.monitoreo_controller.agregar_camara,
            on_camara_quitada=self.monitoreo_controller.quitar_camara,
            programar_arranque_nativo=self.monitoreo_controller.encolar_arranque_nativo,
        )
        self.dvr_controller = DvrController(
            self.main_window.dvr_view, usuario,
            on_camara_agregada=self.monitoreo_controller.agregar_camara,
            on_camara_quitada=self.monitoreo_controller.quitar_camara,
            programar_arranque_nativo=self.monitoreo_controller.encolar_arranque_nativo,
        )
        self.telegram_controller = TelegramController(self.main_window.telegram_view)

    def show(self):
        self.main_window.show()

    def detener(self):
        self.monitoreo_controller.detener()
