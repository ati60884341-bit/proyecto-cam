from PyQt6.QtCore import QTimer

from app.models import incidencia_model
from app.services import alertas_service
from app.views.inicio_view import mensajes_de_compania


class InicioController:
    """Llena el resumen de la pantalla de Inicio (camaras en linea,
    incidencias de hoy, por donde llegan las alertas) mientras se ve."""

    def __init__(self, view, monitoreo_controller, ir_a_monitoreo):
        self.view = view
        self.monitoreo = monitoreo_controller
        self.view.ir_a_monitoreo.connect(ir_a_monitoreo)
        self._timer = QTimer()
        self._timer.timeout.connect(self.actualizar)
        self._timer.start(5000)
        # las camaras tardan unos segundos en conectar: primer resumen al ratito
        QTimer.singleShot(1500, self.actualizar)

    def actualizar(self):
        if not self.view.isVisible():
            return  # nada de consultas mientras se usa otra pestana
        en_linea, total = self.monitoreo.resumen_camaras()
        try:
            incidencias = incidencia_model.contar_hoy()
        except Exception:
            incidencias = "-"
        self.view.set_mensajes(mensajes_de_compania(total))
        self.view.set_resumen(en_linea, total, incidencias, *alertas_service.estado())
