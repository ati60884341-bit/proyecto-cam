import os
import subprocess
import tempfile

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QTextEdit,
    QApplication, QMessageBox,
)

from app.services.actualizador import HiloDescargarActualizacion


class DialogoActualizacion(QDialog):
    """Se muestra cuando HiloBuscarActualizacion encuentra una version mas
    nueva publicada en GitHub. "Actualizar ahora" descarga el instalador
    (con barra de progreso, puede pesar varios cientos de MB por
    PyQt6/opencv/mediapipe) y lo abre - el instalador mismo cierra este
    programa y lo reemplaza (ver installer.iss, CloseApplications)."""

    def __init__(self, info, parent=None):
        super().__init__(parent)
        self.info = info
        self._hilo_descarga = None
        self.setWindowTitle("Actualizacion disponible")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Hay una version nueva de CAM: {info['version']}"))

        notas = QTextEdit()
        notas.setReadOnly(True)
        notas.setPlainText(info.get("notas") or "(sin notas para esta version)")
        notas.setMaximumHeight(140)
        layout.addWidget(notas)

        self.barra_progreso = QProgressBar()
        self.barra_progreso.setRange(0, 100)
        self.barra_progreso.setVisible(False)
        layout.addWidget(self.barra_progreso)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setVisible(False)
        layout.addWidget(self.lbl_estado)

        fila_botones = QHBoxLayout()
        self.btn_mas_tarde = QPushButton("Mas tarde")
        self.btn_mas_tarde.clicked.connect(self.reject)
        fila_botones.addWidget(self.btn_mas_tarde)
        fila_botones.addStretch()
        self.btn_actualizar = QPushButton("Actualizar ahora")
        self.btn_actualizar.setObjectName("btnIngresar")  # mismo acento teal que el boton de login
        self.btn_actualizar.clicked.connect(self._iniciar_descarga)
        fila_botones.addWidget(self.btn_actualizar)
        layout.addLayout(fila_botones)

    def _iniciar_descarga(self):
        self.btn_actualizar.setEnabled(False)
        self.btn_mas_tarde.setEnabled(False)
        self.barra_progreso.setVisible(True)
        self.lbl_estado.setVisible(True)
        self.lbl_estado.setText("Descargando...")

        destino = os.path.join(tempfile.gettempdir(), "CAM_actualizaciones", self.info["nombre_archivo"])
        self._hilo_descarga = HiloDescargarActualizacion(self.info["url_instalador"], destino, self)
        self._hilo_descarga.progreso.connect(self._actualizar_progreso)
        self._hilo_descarga.terminado.connect(self._descarga_lista)
        self._hilo_descarga.fallo.connect(self._descarga_fallo)
        self._hilo_descarga.start()

    def _actualizar_progreso(self, leidos, total):
        leidos_mb = leidos // (1024 * 1024)
        if total:
            self.barra_progreso.setRange(0, 100)
            self.barra_progreso.setValue(int(leidos * 100 / total))
            total_mb = total // (1024 * 1024)
            self.lbl_estado.setText(f"Descargando... {leidos_mb} MB de {total_mb} MB")
        else:
            self.barra_progreso.setRange(0, 0)  # indeterminado: el servidor no informo el tamano
            self.lbl_estado.setText(f"Descargando... {leidos_mb} MB")

    def _descarga_lista(self, ruta_instalador):
        self.lbl_estado.setText("Listo. Abriendo el instalador...")
        try:
            # /CLOSEAPPLICATIONS: el instalador cierra este CAM.exe solo
            # (installer.iss ya trae CloseApplications=yes), sin que haya
            # que pedirle al usuario que lo cierre a mano primero
            subprocess.Popen([ruta_instalador, "/CLOSEAPPLICATIONS"], shell=False)
        except OSError as exc:
            QMessageBox.warning(self, "No se pudo abrir el instalador", str(exc))
            self.btn_actualizar.setEnabled(True)
            self.btn_mas_tarde.setEnabled(True)
            return
        self.accept()
        QApplication.quit()

    def _descarga_fallo(self, mensaje):
        QMessageBox.warning(self, "No se pudo descargar la actualizacion", mensaje)
        self.btn_actualizar.setEnabled(True)
        self.btn_mas_tarde.setEnabled(True)
        self.barra_progreso.setVisible(False)
        self.lbl_estado.setVisible(False)
