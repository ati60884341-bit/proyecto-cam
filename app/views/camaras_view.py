from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)

MARCAS = ["Hikvision", "Dahua", "Tapo", "WebcamUSB", "Generico"]
COLUMNAS = ["ID", "Zona", "Nombre", "Marca", "Conexion", "URL / Indice", "Estado"]


class CamarasView(QWidget):
    """Alta de camaras (adaptador universal multimarca): cualquier camara IP
    de cualquier marca entra por RTSP; las webcams locales, por USB."""

    agregar_solicitado = pyqtSignal(dict)
    quitar_solicitado = pyqtSignal(int)
    refrescar_solicitado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._permitido_quitar = False
        layout = QVBoxLayout(self)

        grupo = QGroupBox("Agregar camara (cualquier marca)")
        formulario = QFormLayout(grupo)

        self.campo_zona = QComboBox()
        self.campo_zona.setEditable(True)
        self.campo_zona.setPlaceholderText("Ingreso / Patio / ... o una zona nueva")
        formulario.addRow("Zona:", self.campo_zona)

        self.campo_nombre = QLineEdit()
        self.campo_nombre.setPlaceholderText("Ej: Cam-Deposito-01")
        formulario.addRow("Nombre:", self.campo_nombre)

        self.campo_marca = QComboBox()
        self.campo_marca.addItems(MARCAS)
        formulario.addRow("Marca:", self.campo_marca)

        self.campo_tipo = QComboBox()
        self.campo_tipo.addItems(["RTSP", "USB"])
        self.campo_tipo.currentTextChanged.connect(self._actualizar_placeholder_url)
        formulario.addRow("Conexion:", self.campo_tipo)

        self.campo_url = QLineEdit()
        formulario.addRow("URL RTSP / indice USB:", self.campo_url)
        self._actualizar_placeholder_url("RTSP")

        self.btn_agregar = QPushButton("Agregar camara")
        self.btn_agregar.clicked.connect(self._emitir_agregar)
        formulario.addRow(self.btn_agregar)

        layout.addWidget(grupo)

        encabezado = QHBoxLayout()
        encabezado.addWidget(QLabel("Camaras registradas"))
        encabezado.addStretch()

        # el boton va en esta fila (y no debajo de la tabla) para que
        # siempre se vea, sin importar el alto de la ventana: la tabla usa
        # el resto del espacio y puede dejar muy poco lugar mas abajo
        self.btn_quitar = QPushButton("Quitar camara seleccionada")
        self.btn_quitar.setStyleSheet(
            "QPushButton { background:#7a1f1f; color:white; } QPushButton:disabled { background:#3a3a3a; color:#888; }"
        )
        self.btn_quitar.setEnabled(False)
        self.btn_quitar.clicked.connect(self._emitir_quitar)
        encabezado.addWidget(self.btn_quitar)

        btn_refrescar = QPushButton("Actualizar")
        btn_refrescar.clicked.connect(self.refrescar_solicitado.emit)
        encabezado.addWidget(btn_refrescar)
        layout.addLayout(encabezado)

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.itemSelectionChanged.connect(self._actualizar_boton_quitar)
        layout.addWidget(self.tabla)

    def _actualizar_placeholder_url(self, tipo):
        if tipo == "USB":
            self.campo_url.setPlaceholderText("0  (indice de la webcam, normalmente 0)")
        else:
            self.campo_url.setPlaceholderText("rtsp://usuario:clave@192.168.1.50:554/stream1")

    def _emitir_agregar(self):
        zona = self.campo_zona.currentText().strip()
        nombre = self.campo_nombre.text().strip()
        url = self.campo_url.text().strip()
        if not zona or not nombre or not url:
            QMessageBox.warning(self, "Faltan datos", "Complete zona, nombre y URL/indice de la camara.")
            return
        self.agregar_solicitado.emit({
            "zona": zona,
            "nombre": nombre,
            "marca": self.campo_marca.currentText(),
            "tipo_conexion": self.campo_tipo.currentText(),
            "url": url,
        })
        self.campo_nombre.clear()
        self.campo_url.clear()

    def _emitir_quitar(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            QMessageBox.information(self, "Quitar camara", "Seleccione una camara de la tabla primero.")
            return
        id_camara = int(self.tabla.item(filas[0].row(), 0).text())
        self.quitar_solicitado.emit(id_camara)

    def _actualizar_boton_quitar(self):
        # currentRow() no se resetea al deseleccionar (son conceptos
        # distintos en Qt): hay que usar hasSelection() para saber de
        # verdad si hay una fila elegida
        self.btn_quitar.setEnabled(self._permitido_quitar and self.tabla.selectionModel().hasSelection())

    def permitir_quitar(self, permitido):
        self._permitido_quitar = permitido
        self.btn_quitar.setVisible(permitido)
        self._actualizar_boton_quitar()

    def set_zonas_disponibles(self, zonas):
        actual = self.campo_zona.currentText()
        self.campo_zona.clear()
        self.campo_zona.addItems(zonas)
        if actual:
            self.campo_zona.setCurrentText(actual)

    def cargar(self, camaras):
        self.tabla.setRowCount(0)
        for fila, c in enumerate(camaras):
            self.tabla.insertRow(fila)
            valores = [
                c["IdCamara"], c["Zona"], c["Nombre"], c["Marca"],
                c["TipoConexion"], c["UrlConexion"], c["Estado"],
            ]
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
