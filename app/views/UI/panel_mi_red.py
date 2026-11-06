from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
)

from app.services.network_info import listar_interfaces_red

COLUMNAS = ["Adaptador de esta PC", "Mi IP", "Mi red (subred)"]


class PanelMiRed(QGroupBox):
    """Panel reutilizable: muestra la IP/subred de ESTA PC en cada adaptador
    de red activo. Se usa en "NVR / DVR" y "Radar de camaras" para que el
    tecnico compare a simple vista si esta en la misma red que la IP del
    DVR/camara que va a escribir, ANTES de perder tiempo armando y probando
    la conexion (el motivo tipico de "no hace ping" en terreno es estar en
    una subred distinta, no un problema del programa)."""

    def __init__(self, parent=None):
        super().__init__("Mi red (esta PC)", parent)
        layout = QVBoxLayout(self)

        encabezado = QHBoxLayout()
        ayuda = QLabel(
            "Compare esto con la IP del DVR/camara: si la \"red\" no coincide\n"
            "(ej. 192.168.1.0/24 vs 192.168.50.0/24), no se van a poder conectar\n"
            "aunque el cable y el DVR esten perfectos."
        )
        ayuda.setStyleSheet("color: #aaa; font-size: 11px;")
        encabezado.addWidget(ayuda)
        encabezado.addStretch()
        btn_actualizar = QPushButton("Actualizar")
        btn_actualizar.clicked.connect(self.actualizar)
        encabezado.addWidget(btn_actualizar)
        layout.addLayout(encabezado)

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setMaximumHeight(110)
        layout.addWidget(self.tabla)

        self.actualizar()

    def actualizar(self):
        interfaces = listar_interfaces_red()
        self.tabla.setRowCount(0)
        if not interfaces:
            self.tabla.setRowCount(1)
            self.tabla.setItem(0, 0, QTableWidgetItem("No se pudo leer la red de esta PC (pruebe 'ipconfig' a mano)."))
            return
        for fila, interfaz in enumerate(interfaces):
            self.tabla.insertRow(fila)
            valores = [interfaz["interfaz"], interfaz["ip"], interfaz.get("red", "")]
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
