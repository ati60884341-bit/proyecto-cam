from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.config import INTERVALO_FATIGA_SEG, TOLERANCIA_FATIGA_SEG


class AuditorFatiga(QObject):
    """Dead man's switch: pide confirmacion periodica al vigilante.
    Si no responde a tiempo, emite fatiga_detectada."""

    pedir_confirmacion = pyqtSignal()
    fatiga_detectada = pyqtSignal()
    confirmado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer_intervalo = QTimer(self)
        self._timer_intervalo.setInterval(INTERVALO_FATIGA_SEG * 1000)
        self._timer_intervalo.timeout.connect(self._solicitar)

        self._timer_tolerancia = QTimer(self)
        self._timer_tolerancia.setSingleShot(True)
        self._timer_tolerancia.setInterval(TOLERANCIA_FATIGA_SEG * 1000)
        self._timer_tolerancia.timeout.connect(self._marcar_fatiga)

    def iniciar(self):
        self._timer_intervalo.start()

    def detener(self):
        self._timer_intervalo.stop()
        self._timer_tolerancia.stop()

    def _solicitar(self):
        self.pedir_confirmacion.emit()
        self._timer_tolerancia.start()

    def _marcar_fatiga(self):
        self.fatiga_detectada.emit()

    def confirmar(self):
        if self._timer_tolerancia.isActive():
            self._timer_tolerancia.stop()
            self.confirmado.emit()
