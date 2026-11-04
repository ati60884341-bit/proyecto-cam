from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QTextEdit,
)

MARCAS_DVR = ["Hikvision", "Dahua"]
COLUMNAS = ["ID", "Nombre", "Marca", "IP", "Canales", "Camaras activas"]


class DvrView(QWidget):
    """Pestana "NVR / DVR": a diferencia de "Camaras" (una camara IP/USB a
    la vez), aqui se registra el GRABADOR (el DVR o NVR fisico, con sus
    varios canales/camaras conectadas) una sola vez, y el sistema agrega
    automaticamente una camara por cada canal que responda - igual que
    hace el software del fabricante (iVMS-4200 de Hikvision, SmartPSS de
    Dahua, etc.) al "buscar" los canales de un grabador."""

    registrar_solicitado = pyqtSignal(dict)
    detectar_nuevos_solicitado = pyqtSignal(int)
    quitar_solicitado = pyqtSignal(int)
    refrescar_solicitado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._permitido_quitar = False
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Un DVR (para camaras analogicas) o NVR (para camaras IP) es un grabador con varios\n"
            "canales, cada uno con su propia camara conectada. En vez de agregar canal por canal,\n"
            "registre aqui el grabador UNA sola vez (IP, usuario, clave y cuantos canales tiene) y\n"
            "el sistema prueba cada canal y agrega sola una camara por cada uno que responda —\n"
            "asi se ve en el Centro de Monitoreo TODO lo que esta conectado al grabador."
        )
        layout.addWidget(intro)

        grupo = QGroupBox("Registrar un DVR/NVR nuevo")
        formulario = QFormLayout(grupo)

        self.campo_nombre = QLineEdit()
        self.campo_nombre.setPlaceholderText("Ej: DVR Patio Central  (tambien se usa para nombrar sus zonas/camaras)")
        formulario.addRow("Nombre:", self.campo_nombre)

        self.campo_marca = QComboBox()
        self.campo_marca.addItems(MARCAS_DVR)
        formulario.addRow("Marca:", self.campo_marca)

        self.campo_ip = QLineEdit()
        self.campo_ip.setPlaceholderText("Ej: 192.168.1.64")
        formulario.addRow("IP del grabador:", self.campo_ip)

        self.campo_puerto = QLineEdit("554")
        formulario.addRow("Puerto RTSP:", self.campo_puerto)

        self.campo_usuario = QLineEdit("admin")
        formulario.addRow("Usuario:", self.campo_usuario)

        self.campo_clave = QLineEdit()
        self.campo_clave.setEchoMode(QLineEdit.EchoMode.Password)
        formulario.addRow("Clave:", self.campo_clave)

        self.campo_canales = QLineEdit("4")
        self.campo_canales.setPlaceholderText("Cuantos canales/camaras tiene el grabador")
        formulario.addRow("Cantidad de canales:", self.campo_canales)

        self.chk_ptz = QCheckBox("Todos los canales son domos PTZ (pueden moverse)")
        self.chk_ptz.setToolTip(
            "Marquelo solo si TODOS los canales de este grabador son camaras con motor\n"
            "PTZ. La mayoria de instalaciones usan camaras fijas: si mezcla domos PTZ con\n"
            "camaras fijas en el mismo grabador, agregue las PTZ por separado desde la\n"
            "pestana \"Camaras\" para marcarlas una por una."
        )
        formulario.addRow(self.chk_ptz)

        self.btn_registrar = QPushButton("Registrar y detectar todos los canales")
        self.btn_registrar.clicked.connect(self._emitir_registrar)
        formulario.addRow(self.btn_registrar)

        self.lbl_progreso = QLabel("")
        formulario.addRow(self.lbl_progreso)

        layout.addWidget(grupo)

        encabezado = QHBoxLayout()
        encabezado.addWidget(QLabel("Grabadores (DVR/NVR) registrados"))
        encabezado.addStretch()

        self.btn_detectar_nuevos = QPushButton("Detectar canales nuevos")
        self.btn_detectar_nuevos.setEnabled(False)
        self.btn_detectar_nuevos.clicked.connect(self._emitir_detectar_nuevos)
        encabezado.addWidget(self.btn_detectar_nuevos)

        self.btn_quitar = QPushButton("Quitar grabador y sus camaras")
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
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones_fila)
        layout.addWidget(self.tabla)

        layout.addWidget(QLabel("Registro de deteccion de canales:"))
        self.texto_log = QTextEdit()
        self.texto_log.setReadOnly(True)
        self.texto_log.setMaximumHeight(140)
        layout.addWidget(self.texto_log)

    # ---------------- registrar + detectar ----------------
    def _emitir_registrar(self):
        nombre = self.campo_nombre.text().strip()
        ip = self.campo_ip.text().strip()
        if not nombre or not ip:
            QMessageBox.warning(self, "Faltan datos", "Complete el nombre y la IP del grabador.")
            return
        try:
            cantidad_canales = int(self.campo_canales.text().strip() or "4")
        except ValueError:
            QMessageBox.warning(self, "Dato invalido", "La cantidad de canales debe ser un numero.")
            return
        if cantidad_canales < 1 or cantidad_canales > 64:
            QMessageBox.warning(self, "Dato invalido", "La cantidad de canales debe estar entre 1 y 64.")
            return
        self.registrar_solicitado.emit({
            "nombre": nombre,
            "marca": self.campo_marca.currentText(),
            "ip": ip,
            "puerto": self.campo_puerto.text().strip() or "554",
            "usuario": self.campo_usuario.text().strip() or "admin",
            "clave": self.campo_clave.text(),
            "cantidad_canales": cantidad_canales,
            "tiene_ptz": self.chk_ptz.isChecked(),
        })

    def set_detectando(self, activo, total=0):
        self.btn_registrar.setEnabled(not activo)
        self.btn_detectar_nuevos.setEnabled(not activo and self._permitido_quitar and self.tabla.selectionModel().hasSelection())
        if activo:
            self.lbl_progreso.setText(f"Probando canal 1 de {total}...")
        else:
            self.lbl_progreso.setText("")

    def actualizar_progreso(self, canal_actual, total):
        self.lbl_progreso.setText(f"Probando canal {canal_actual} de {total}...")

    def registrar_evento(self, texto):
        self.texto_log.append(texto)

    # ---------------- tabla de grabadores ----------------
    def _id_seleccionado(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return int(self.tabla.item(filas[0].row(), 0).text())

    def _emitir_detectar_nuevos(self):
        id_dispositivo = self._id_seleccionado()
        if id_dispositivo is None:
            QMessageBox.information(self, "Detectar canales nuevos", "Seleccione un grabador de la tabla primero.")
            return
        self.detectar_nuevos_solicitado.emit(id_dispositivo)

    def _emitir_quitar(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            QMessageBox.information(self, "Quitar grabador", "Seleccione un grabador de la tabla primero.")
            return
        fila = filas[0].row()
        id_dispositivo = int(self.tabla.item(fila, 0).text())
        nombre = self.tabla.item(fila, 1).text()
        confirmacion = QMessageBox.question(
            self, "Confirmar",
            f"¿Quitar el grabador \"{nombre}\" y TODAS sus camaras (se detienen sus hilos y "
            "quedan marcadas como inactivas)?",
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        self.quitar_solicitado.emit(id_dispositivo)

    def _actualizar_botones_fila(self):
        hay_seleccion = self.tabla.selectionModel().hasSelection()
        self.btn_quitar.setEnabled(self._permitido_quitar and hay_seleccion)
        self.btn_detectar_nuevos.setEnabled(self._permitido_quitar and hay_seleccion)

    def permitir_quitar(self, permitido):
        self._permitido_quitar = permitido
        self.btn_quitar.setVisible(permitido)
        self.btn_detectar_nuevos.setVisible(permitido)
        self._actualizar_botones_fila()

    def cargar(self, dispositivos):
        self.tabla.setRowCount(0)
        for fila, d in enumerate(dispositivos):
            self.tabla.insertRow(fila)
            valores = [
                d["IdDispositivo"], d["Nombre"], d["Marca"], d["IP"],
                d["CantidadCanales"], d["CamarasActivas"],
            ]
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
