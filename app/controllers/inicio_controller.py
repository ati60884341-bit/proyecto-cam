from PySide6.QtCore import QThread, QTimer, Signal

from app.models import incidencia_model
from app.views.inicio_view import mensajes_de_compania


class _ConsultaIncidenciasThread(QThread):
    """Cuenta las incidencias de hoy en un hilo aparte: contar_hoy() viaja a
    la base de datos, y pedirlo cada 5 s desde el hilo de la UI (como antes)
    la trababa un instante cada vez, sobre todo con la pantalla de Inicio
    animada de fondo."""
    listo = Signal(object)

    def run(self):
        try:
            self.listo.emit(incidencia_model.contar_hoy())
        except Exception:
            self.listo.emit("-")


class InicioController:
    """Llena el resumen de la pantalla de Inicio (camaras en linea,
    incidencias de hoy) mientras se ve."""

    def __init__(self, view, monitoreo_controller, ir_a_monitoreo):
        self.view = view
        self.monitoreo = monitoreo_controller
        self.view.ir_a_monitoreo.connect(ir_a_monitoreo)
        self._incidencias_hoy = "..."
        self._hilo_incidencias = None
        self._timer = QTimer()
        self._timer.timeout.connect(self.actualizar)
        self._timer.start(5000)
        # las camaras tardan unos segundos en conectar: primer resumen al ratito
        QTimer.singleShot(1500, self.actualizar)

    def actualizar(self):
        if not self.view.isVisible():
            return  # nada de consultas mientras se usa otra pestana
        en_linea, total = self.monitoreo.resumen_camaras()
        self.view.set_mensajes(mensajes_de_compania(total))
        self.view.set_resumen(en_linea, total, self._incidencias_hoy)
        self._consultar_incidencias()

    def _consultar_incidencias(self):
        if self._hilo_incidencias is not None:
            return  # ya hay una consulta en curso (base lenta): no se acumulan
        hilo = _ConsultaIncidenciasThread()
        hilo.listo.connect(self._incidencias_listas)
        hilo.finished.connect(self._liberar_hilo_incidencias)
        self._hilo_incidencias = hilo
        hilo.start()

    def _liberar_hilo_incidencias(self):
        self._hilo_incidencias = None

    def _incidencias_listas(self, total):
        self._incidencias_hoy = total
        en_linea, total_camaras = self.monitoreo.resumen_camaras()
        self.view.set_resumen(en_linea, total_camaras, total)

    def detener(self):
        """Se llama al cerrar sesion: sin esto, el timer de 5 s seguia
        corriendo y una consulta de incidencias en curso podia terminar
        despues de cerrada la ventana e intentar escribir en una vista ya
        destruida (o, si el usuario volvia a entrar rapido, en la vista
        de la sesion nueva)."""
        self._timer.stop()
        if self._hilo_incidencias is not None:
            try:
                self._hilo_incidencias.listo.disconnect(self._incidencias_listas)
            except (TypeError, RuntimeError):
                pass
