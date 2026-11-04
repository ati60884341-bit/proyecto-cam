from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)

from app.services.dvr_urls import construir_url_canal, MARCAS_CON_ASISTENTE_DVR

MARCAS = ["Hikvision", "Dahua", "Tapo", "WebcamUSB", "Generico"]
COLUMNAS = ["ID", "Zona", "Nombre", "Marca", "Conexion", "URL / Indice", "Estado", "PTZ"]


class CamarasView(QWidget):
    """Alta de camaras (adaptador universal multimarca): cualquier camara IP
    de cualquier marca entra por RTSP; las webcams locales, por USB."""

    agregar_solicitado = pyqtSignal(dict)
    quitar_solicitado = pyqtSignal(int)
    refrescar_solicitado = pyqtSignal()
    probar_solicitado = pyqtSignal(dict)
    detectar_usb_solicitado = pyqtSignal()

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
        self.campo_marca.currentTextChanged.connect(self._actualizar_asistente_dvr)
        formulario.addRow("Marca:", self.campo_marca)

        self.campo_tipo = QComboBox()
        self.campo_tipo.addItems(["RTSP", "USB"])
        self.campo_tipo.currentTextChanged.connect(self._actualizar_placeholder_url)
        self.campo_tipo.currentTextChanged.connect(self._actualizar_asistente_dvr)
        formulario.addRow("Conexion:", self.campo_tipo)

        # Asistente Hikvision/Dahua: completando esto, la URL de abajo se
        # arma sola (nadie tiene que memorizar el formato RTSP del DVR).
        self.grupo_asistente = QGroupBox("Asistente de conexion al DVR (completa esto y la URL se arma sola)")
        formulario_asistente = QFormLayout(self.grupo_asistente)

        self.campo_ip = QLineEdit()
        self.campo_ip.setPlaceholderText("Ej: 192.168.1.64")
        formulario_asistente.addRow("IP del DVR/camara:", self.campo_ip)

        self.campo_puerto = QLineEdit("554")
        formulario_asistente.addRow("Puerto RTSP:", self.campo_puerto)

        self.campo_usuario_dvr = QLineEdit("admin")
        formulario_asistente.addRow("Usuario:", self.campo_usuario_dvr)

        self.campo_clave_dvr = QLineEdit()
        self.campo_clave_dvr.setEchoMode(QLineEdit.EchoMode.Password)
        formulario_asistente.addRow("Clave:", self.campo_clave_dvr)

        self.campo_canal = QLineEdit("1")
        formulario_asistente.addRow("Canal (1, 2, 3...):", self.campo_canal)

        self.campo_flujo = QComboBox()
        self.campo_flujo.addItems(["Principal (mejor calidad)", "Secundario (mas liviano)"])
        formulario_asistente.addRow("Calidad de video:", self.campo_flujo)

        aviso_multicanal = QLabel(
            "¿Este grabador tiene MAS de una cámara/canal? Use la pestaña \"NVR / DVR\"\n"
            "en vez de esto: registra el grabador una sola vez y agrega todos sus\n"
            "canales de un tirón. Use este asistente solo para una cámara suelta."
        )
        aviso_multicanal.setStyleSheet("color: #aaa; font-size: 11px;")
        aviso_multicanal.setWordWrap(True)
        formulario_asistente.addRow(aviso_multicanal)

        for campo in (self.campo_ip, self.campo_puerto, self.campo_usuario_dvr, self.campo_clave_dvr, self.campo_canal):
            campo.textChanged.connect(self._actualizar_url_desde_asistente)
        self.campo_flujo.currentIndexChanged.connect(self._actualizar_url_desde_asistente)

        formulario.addRow(self.grupo_asistente)

        self.campo_url = QLineEdit()
        formulario.addRow("URL RTSP / indice USB:", self.campo_url)

        # Deteccion de camaras USB: el indice de la webcam cambia de laptop a
        # laptop (la integrada puede ser 0, 1 o 2 segun el equipo), asi que
        # en vez de adivinar se prueban todas y se eligen de una lista.
        fila_usb = QHBoxLayout()
        self.btn_detectar_usb = QPushButton("Detectar camaras USB disponibles")
        self.btn_detectar_usb.clicked.connect(self._emitir_detectar_usb)
        fila_usb.addWidget(self.btn_detectar_usb)

        self.combo_usb_detectadas = QComboBox()
        self.combo_usb_detectadas.setPlaceholderText("(pulse Detectar)")
        self.combo_usb_detectadas.currentIndexChanged.connect(self._elegir_usb_detectada)
        fila_usb.addWidget(self.combo_usb_detectadas)
        self.fila_usb_widget = QWidget()
        self.fila_usb_widget.setLayout(fila_usb)
        formulario.addRow(self.fila_usb_widget)

        self.chk_ptz = QCheckBox("Esta camara tiene motor PTZ (puede moverse: izq/der/arriba/abajo, con presets)")
        self.chk_ptz.setToolTip(
            "Marquelo solo si el modelo exacto tiene motor de movimiento. La mayoria de camaras\n"
            "fijas/bullet NO lo tienen, incluso siendo de una marca que si vende domos PTZ.\n"
            "Si no esta seguro, dejelo sin marcar: no afecta la deteccion de sabotaje ni el video."
        )
        formulario.addRow(self.chk_ptz)

        self._actualizar_placeholder_url("RTSP")
        self._actualizar_asistente_dvr()

        fila_botones = QHBoxLayout()
        self.btn_agregar = QPushButton("Agregar camara")
        self.btn_agregar.clicked.connect(self._emitir_agregar)
        fila_botones.addWidget(self.btn_agregar)

        self.btn_probar = QPushButton("Probar conexion")
        self.btn_probar.clicked.connect(self._emitir_probar)
        fila_botones.addWidget(self.btn_probar)
        formulario.addRow(fila_botones)

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
        self.fila_usb_widget.setVisible(tipo == "USB")
        if tipo == "USB":
            self.campo_url.setPlaceholderText("0  (indice de la webcam, normalmente 0)")
        else:
            self.campo_url.setPlaceholderText("rtsp://usuario:clave@192.168.1.50:554/stream1")

    def _emitir_detectar_usb(self):
        self.detectar_usb_solicitado.emit()

    def set_detectando_usb(self, activo):
        self.btn_detectar_usb.setEnabled(not activo)
        self.btn_detectar_usb.setText("Detectando..." if activo else "Detectar camaras USB disponibles")

    def mostrar_camaras_usb_detectadas(self, encontradas):
        self.combo_usb_detectadas.clear()
        if not encontradas:
            self.combo_usb_detectadas.addItem("Ninguna camara respondio", None)
            QMessageBox.warning(
                self, "Deteccion de camaras USB",
                "No se encontro ninguna camara USB/integrada en los indices 0 a 4. "
                "Verifique que este conectada y que ninguna otra app (Zoom, Teams, etc.) la este usando.",
            )
            return
        for c in encontradas:
            self.combo_usb_detectadas.addItem(f"Indice {c['indice']} ({c['resolucion']})", c["indice"])

    def _elegir_usb_detectada(self, _posicion):
        indice = self.combo_usb_detectadas.currentData()
        if indice is not None:
            self.campo_url.setText(str(indice))

    def _actualizar_asistente_dvr(self):
        mostrar = (
            self.campo_marca.currentText() in MARCAS_CON_ASISTENTE_DVR
            and self.campo_tipo.currentText() == "RTSP"
        )
        self.grupo_asistente.setVisible(mostrar)
        if mostrar:
            self._actualizar_url_desde_asistente()

    def _actualizar_url_desde_asistente(self):
        if not self.grupo_asistente.isVisible():
            return
        url = construir_url_canal(
            self.campo_marca.currentText(),
            self.campo_ip.text().strip(),
            self.campo_puerto.text().strip(),
            self.campo_usuario_dvr.text().strip(),
            self.campo_clave_dvr.text(),
            self.campo_canal.text().strip(),
            self.campo_flujo.currentIndex() == 0,
        )
        if url:
            self.campo_url.setText(url)

    def _emitir_probar(self):
        tipo = self.campo_tipo.currentText()
        url = self.campo_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Falta la URL", "Complete la URL RTSP (o el indice USB) antes de probar.")
            return
        self.probar_solicitado.emit({"tipo_conexion": tipo, "url": url})

    def set_probando(self, activo):
        self.btn_probar.setEnabled(not activo)
        self.btn_probar.setText("Probando..." if activo else "Probar conexion")

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
            "tiene_ptz": self.chk_ptz.isChecked(),
        })
        self.campo_nombre.clear()
        self.campo_url.clear()
        self.chk_ptz.setChecked(False)

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
                "Si" if c.get("TienePTZ") else "No",
            ]
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
