from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QMessageBox

from app.models import evidencia_model


class EvidenciaController:
    def __init__(self, view, usuario):
        self.view = view
        self.usuario = usuario
        self.view.refrescar_solicitado.connect(self.cargar)
        self.view.ver_solicitado.connect(self.ver)
        self.view.eliminar_solicitado.connect(self.eliminar)
        self.view.permitir_eliminar(usuario["Rol"] == "Administrador")
        self._evidencias = []
        self.cargar()

    def cargar(self):
        self._evidencias = evidencia_model.listar()
        self.view.cargar(self._evidencias)

    def _buscar(self, id_evidencia):
        return next((e for e in self._evidencias if e["IdEvidencia"] == id_evidencia), None)

    def ver(self, id_evidencia):
        evidencia = self._buscar(id_evidencia)
        if not evidencia:
            return
        if evidencia["TipoArchivo"] != "Foto":
            QMessageBox.information(self.view, "Evidencia", "Esta evidencia es un video; ábralo desde su carpeta.")
            return
        pixmap = QPixmap(evidencia["RutaArchivo"])
        if pixmap.isNull():
            QMessageBox.warning(self.view, "Evidencia", "No se pudo abrir el archivo de imagen.")
            return
        dialogo = QDialog(self.view)
        dialogo.setWindowTitle(f"Evidencia #{id_evidencia} - {evidencia['Zona']}")
        layout = QVBoxLayout(dialogo)
        etiqueta = QLabel()
        etiqueta.setPixmap(pixmap.scaledToWidth(640))
        layout.addWidget(etiqueta)
        layout.addWidget(QLabel(f"SHA-256: {evidencia['HashSHA256']}"))
        dialogo.exec()

    def eliminar(self, id_evidencia):
        if self.usuario["Rol"] != "Administrador":
            QMessageBox.warning(self.view, "Permiso denegado", "Solo un administrador puede eliminar evidencias.")
            return
        confirmacion = QMessageBox.question(
            self.view, "Confirmar", "¿Eliminar esta evidencia de forma permanente?"
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        ok, mensaje = evidencia_model.eliminar(id_evidencia)
        if ok:
            QMessageBox.information(self.view, "Evidencia", mensaje)
        else:
            QMessageBox.warning(self.view, "Bloqueado por cadena de custodia", mensaje)
        self.cargar()
