from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QTextEdit,
)

COLUMNAS = ["IP", "Marca", "Modelo", "Tipo detectado", "Canales", "Como se encontro"]


class RadarView(QWidget):
    """Pestana "Radar de camaras": busca automaticamente camaras/grabadores
    en la red local (sin que el usuario tenga que saber su IP de antemano),
    igual que SADP de Hikvision o el buscador de ConfigTool de Dahua.

    Deteccion "de buena fe": la marca/modelo son reales (el equipo se
    identifica solo via ONVIF), pero "camara suelta" vs "grabador" es una
    estimacion por cantidad de canales - el usuario confirma o corrige al
    agregarlo de verdad desde "Camaras" o "NVR / DVR"."""

    escanear_solicitado = pyqtSignal(dict)  # {escaneo_completo, usuario, clave}
    reintentar_solicitado = pyqtSignal(dict)  # {ip, usuario, clave}
    usar_en_camaras_solicitado = pyqtSignal(dict)
    usar_en_dvr_solicitado = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dispositivos = []
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Busca camaras/grabadores encendidos en esta misma red (no hace falta saber su IP).\n"
            "La marca y el modelo son reales (el equipo se identifica solo); si es una camara suelta\n"
            "o un grabador con varios canales es una ESTIMACION — confirmela al agregarlo de verdad."
        )
        layout.addWidget(intro)

        fila_controles = QHBoxLayout()
        self.btn_escanear = QPushButton("Iniciar escaneo")
        self.btn_escanear.clicked.connect(self._emitir_escanear)
        fila_controles.addWidget(self.btn_escanear)

        self.chk_completo = QCheckBox("Escaneo completo (revisar toda la red por el puerto 554, mas lento)")
        self.chk_completo.setToolTip(
            "Ademas de la busqueda ONVIF (rapida, unos segundos), revisa las 254 direcciones\n"
            "de la red por el puerto de video (554): encuentra equipos con ONVIF apagado,\n"
            "pero tarda mas (hasta 1 minuto) y no siempre consigue marca/modelo."
        )
        fila_controles.addWidget(self.chk_completo)
        fila_controles.addStretch()
        layout.addLayout(fila_controles)

        fila_credenciales = QHBoxLayout()
        fila_credenciales.addWidget(QLabel("Usuario (opcional):"))
        self.campo_usuario = QLineEdit()
        self.campo_usuario.setPlaceholderText("admin")
        fila_credenciales.addWidget(self.campo_usuario)
        fila_credenciales.addWidget(QLabel("Clave (opcional):"))
        self.campo_clave = QLineEdit()
        self.campo_clave.setEchoMode(QLineEdit.EchoMode.Password)
        fila_credenciales.addWidget(self.campo_clave)
        ayuda_credenciales = QLabel(
            "Algunas camaras (ej. Tapo) solo se identifican si se les manda usuario/clave:\n"
            "use la \"Cuenta de camara\" de esa marca, no la de la app del celular."
        )
        ayuda_credenciales.setStyleSheet("color: #aaa; font-size: 11px;")
        fila_credenciales.addWidget(ayuda_credenciales)
        fila_credenciales.addStretch()
        layout.addLayout(fila_credenciales)

        self.lbl_progreso = QLabel("")
        layout.addWidget(self.lbl_progreso)

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones_fila)
        layout.addWidget(self.tabla)

        fila_acciones = QHBoxLayout()
        fila_acciones.addWidget(QLabel("Con la fila seleccionada:"))
        self.btn_usar_camaras = QPushButton("Usar en \"Camaras\" (camara suelta)")
        self.btn_usar_camaras.setEnabled(False)
        self.btn_usar_camaras.clicked.connect(self._emitir_usar_en_camaras)
        fila_acciones.addWidget(self.btn_usar_camaras)

        self.btn_usar_dvr = QPushButton("Usar en \"NVR / DVR\" (grabador)")
        self.btn_usar_dvr.setEnabled(False)
        self.btn_usar_dvr.clicked.connect(self._emitir_usar_en_dvr)
        fila_acciones.addWidget(self.btn_usar_dvr)

        self.btn_reintentar = QPushButton("Reintentar con estas credenciales")
        self.btn_reintentar.setToolTip(
            "Vuelve a consultar SOLO esta fila con el usuario/clave de arriba, sin repetir\n"
            "todo el escaneo - util si quedo 'Desconocida' por pedir autenticacion (ej. Tapo)."
        )
        self.btn_reintentar.setEnabled(False)
        self.btn_reintentar.clicked.connect(self._emitir_reintentar)
        fila_acciones.addWidget(self.btn_reintentar)
        fila_acciones.addStretch()
        layout.addLayout(fila_acciones)

        layout.addWidget(QLabel("Detalle:"))
        self.texto_detalle = QTextEdit()
        self.texto_detalle.setReadOnly(True)
        self.texto_detalle.setMaximumHeight(90)
        layout.addWidget(self.texto_detalle)

    # ---------------- escaneo ----------------
    def _emitir_escanear(self):
        self.tabla.setRowCount(0)
        self._dispositivos = []
        self.texto_detalle.clear()
        self.escanear_solicitado.emit({
            "escaneo_completo": self.chk_completo.isChecked(),
            "usuario": self.campo_usuario.text().strip() or "admin",
            "clave": self.campo_clave.text(),
        })

    def set_escaneando(self, activo):
        self.btn_escanear.setEnabled(not activo)
        self.chk_completo.setEnabled(not activo)
        self.btn_escanear.setText("Escaneando..." if activo else "Iniciar escaneo")

    def actualizar_progreso(self, texto):
        self.lbl_progreso.setText(texto)

    def agregar_dispositivo(self, info):
        """Se llama una vez por cada hallazgo, a medida que van llegando
        (no espera a que termine todo el escaneo) para que la tabla se
        vaya llenando en vivo, como un radar de verdad. Si ya habia una
        fila con esa IP (ej. un "Reintentar con credenciales"), la
        actualiza en el lugar en vez de duplicarla."""
        fila_existente = next((i for i, d in enumerate(self._dispositivos) if d["ip"] == info["ip"]), None)
        if fila_existente is not None:
            self._dispositivos[fila_existente] = info
            fila = fila_existente
        else:
            self._dispositivos.append(info)
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)

        valores = [
            info["ip"], info["marca"], info["modelo"], info["tipo_estimado"],
            info["canales_detectados"], info["metodo"],
        ]
        for columna, valor in enumerate(valores):
            self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
        self._actualizar_botones_fila()

    # ---------------- seleccion y acciones ----------------
    def _dispositivo_seleccionado(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        indice = filas[0].row()
        if indice < len(self._dispositivos):
            return self._dispositivos[indice]
        return None

    def _actualizar_botones_fila(self):
        info = self._dispositivo_seleccionado()
        habilitado = info is not None
        self.btn_usar_camaras.setEnabled(habilitado)
        self.btn_usar_dvr.setEnabled(habilitado)
        self.btn_reintentar.setEnabled(habilitado)
        if info:
            detalle = (
                f"IP: {info['ip']}   Puerto ONVIF: {info.get('puerto_onvif') or '(no detectado)'}\n"
                f"Firmware: {info.get('firmware') or '(desconocido)'}   "
                f"Numero de serie: {info.get('numero_serie') or '(desconocido)'}"
            )
            self.texto_detalle.setPlainText(detalle)
        else:
            self.texto_detalle.clear()

    def _credenciales_escritas(self):
        """Usuario/clave que el usuario ya escribio en esta pestana (por
        ejemplo para el "Reintentar con estas credenciales") - se llevan a
        "Camaras"/"NVR-DVR" para no hacerle escribirlas dos veces, en vez
        de dejar ahi un "usuario:clave" de relleno que no sirve."""
        return self.campo_usuario.text().strip(), self.campo_clave.text()

    def _emitir_usar_en_camaras(self):
        info = self._dispositivo_seleccionado()
        if not info:
            return
        usuario, clave = self._credenciales_escritas()
        self.usar_en_camaras_solicitado.emit(dict(info, usuario=usuario, clave=clave))

    def _emitir_usar_en_dvr(self):
        info = self._dispositivo_seleccionado()
        if not info:
            return
        if info["canales_detectados"] <= 1:
            confirmacion = QMessageBox.question(
                self, "Confirmar",
                "Este equipo parece una camara suelta (1 sola fuente de video detectada), "
                "no un grabador. ¿Usarlo en \"NVR / DVR\" de todas formas?",
            )
            if confirmacion != QMessageBox.StandardButton.Yes:
                return
        usuario, clave = self._credenciales_escritas()
        self.usar_en_dvr_solicitado.emit(dict(info, usuario=usuario, clave=clave))

    def _emitir_reintentar(self):
        info = self._dispositivo_seleccionado()
        if not info:
            return
        self.reintentar_solicitado.emit({
            "ip": info["ip"],
            "usuario": self.campo_usuario.text().strip() or "admin",
            "clave": self.campo_clave.text(),
        })
