from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QHeaderView,
)

COLUMNAS = ["ID Turno", "Usuario", "Duracion (min)", "Cierre"]


class TurnosView(QWidget):
    abrir_turno_solicitado = pyqtSignal()
    cerrar_turno_solicitado = pyqtSignal()
    refrescar_solicitado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.lbl_estado = QLabel("Sin turno abierto.")
        self.lbl_estado.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_estado)

        fila_botones = QHBoxLayout()
        self.btn_abrir = QPushButton("Abrir turno")
        self.btn_abrir.clicked.connect(self.abrir_turno_solicitado.emit)
        fila_botones.addWidget(self.btn_abrir)
        self.btn_cerrar = QPushButton("Cerrar turno")
        self.btn_cerrar.clicked.connect(self.cerrar_turno_solicitado.emit)
        self.btn_cerrar.setEnabled(False)
        fila_botones.addWidget(self.btn_cerrar)
        layout.addLayout(fila_botones)

        layout.addWidget(QLabel("Historial de turnos cerrados (registrado automaticamente por trigger):"))
        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla)

    def set_turno_abierto(self, abierto):
        self.btn_abrir.setEnabled(not abierto)
        self.btn_cerrar.setEnabled(abierto)
        self.lbl_estado.setText("Turno ABIERTO" if abierto else "Sin turno abierto.")

    def cargar_historial(self, historial):
        self.tabla.setRowCount(0)
        for fila, h in enumerate(historial):
            self.tabla.insertRow(fila)
            valores = [h["IdTurno"], h["Usuario"], h["DuracionMinutos"], str(h["FechaCierre"])[:19]]
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
