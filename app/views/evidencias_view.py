from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QHeaderView,
)

COLUMNAS = ["ID", "Zona", "Tipo", "Archivo", "Firma SHA-256", "Fecha", "Usuario"]


class EvidenciasView(QWidget):
    refrescar_solicitado = pyqtSignal()
    ver_solicitado = pyqtSignal(int)
    eliminar_solicitado = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        encabezado = QHBoxLayout()
        encabezado.addWidget(QLabel("Evidencias capturadas (firmadas con SHA-256, cadena de custodia legal)"))
        btn_refrescar = QPushButton("Actualizar")
        btn_refrescar.clicked.connect(self.refrescar_solicitado.emit)
        encabezado.addWidget(btn_refrescar)
        layout.addLayout(encabezado)

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla)

        fila_botones = QHBoxLayout()
        self.btn_ver = QPushButton("Ver imagen")
        self.btn_ver.clicked.connect(lambda: self._emitir(self.ver_solicitado))
        fila_botones.addWidget(self.btn_ver)
        self.btn_eliminar = QPushButton("Eliminar (solo Administrador)")
        self.btn_eliminar.clicked.connect(lambda: self._emitir(self.eliminar_solicitado))
        fila_botones.addWidget(self.btn_eliminar)
        layout.addLayout(fila_botones)

    def cargar(self, evidencias):
        self.tabla.setRowCount(0)
        for fila, ev in enumerate(evidencias):
            self.tabla.insertRow(fila)
            valores = [
                ev["IdEvidencia"], ev["Zona"], ev["TipoArchivo"], ev["RutaArchivo"],
                ev["HashSHA256"], str(ev["FechaCaptura"])[:19], ev["Usuario"] or "",
            ]
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))

    def _emitir(self, senal):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        id_evidencia = int(self.tabla.item(fila, 0).text())
        senal.emit(id_evidencia)

    def permitir_eliminar(self, permitido):
        self.btn_eliminar.setVisible(permitido)
