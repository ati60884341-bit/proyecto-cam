from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QHeaderView,
)

COLUMNAS = ["ID", "Zona", "Tipo", "Severidad", "Descripcion", "Fecha/Hora", "Atendida"]


class IncidenciasView(QWidget):
    refrescar_solicitado = pyqtSignal()
    atender_solicitado = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        encabezado = QHBoxLayout()
        encabezado.addWidget(QLabel("Incidencias registradas (sabotajes, panico, fatiga, manuales)"))
        btn_refrescar = QPushButton("Actualizar")
        btn_refrescar.clicked.connect(self.refrescar_solicitado.emit)
        encabezado.addWidget(btn_refrescar)
        layout.addLayout(encabezado)

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla)

        self.btn_atender = QPushButton("Marcar seleccionada como atendida")
        self.btn_atender.clicked.connect(self._emitir_atender)
        layout.addWidget(self.btn_atender)

    def cargar(self, incidencias):
        self.tabla.setRowCount(0)
        for fila, inc in enumerate(incidencias):
            self.tabla.insertRow(fila)
            valores = [
                inc["IdIncidencia"], inc["Zona"], inc["Tipo"], inc["Severidad"],
                inc["Descripcion"] or "", str(inc["FechaHora"])[:19],
                "Si" if inc["Atendida"] else "No",
            ]
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))

    def _emitir_atender(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        id_incidencia = int(self.tabla.item(fila, 0).text())
        self.atender_solicitado.emit(id_incidencia)
