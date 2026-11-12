from PyQt6.QtCore import QSize, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)

from app.services.dvr_urls import construir_url_canal
from app.views.UI.desplegable import Desplegable
from app.views.UI.iconos import icono

MARCAS_IP = ["Hikvision", "Dahua", "Tapo", "Generico"]
TIPO_IP = "Camara IP (WiFi o cable de red)"
TIPO_USB = "Webcam USB (conectada a esta PC)"
COLUMNAS = ["ID", "Nombre", "Grupo", "Marca", "Conexion", "Enlace / Indice", "Estado", "PTZ"]
# enlaces modelo: el usuario reemplaza USUARIO, CLAVE e IP por los de su camara
ENLACES_MODELO = [
    ("Hikvision - calidad alta", "rtsp://USUARIO:CLAVE@IP:554/Streaming/Channels/101"),
    ("Hikvision - calidad liviana", "rtsp://USUARIO:CLAVE@IP:554/Streaming/Channels/102"),
    ("Dahua - calidad alta", "rtsp://USUARIO:CLAVE@IP:554/cam/realmonitor?channel=1&subtype=0"),
    ("Dahua - calidad liviana", "rtsp://USUARIO:CLAVE@IP:554/cam/realmonitor?channel=1&subtype=1"),
    ("Tapo (TP-Link) - calidad alta", "rtsp://USUARIO:CLAVE@IP:554/stream1"),
    ("Tapo (TP-Link) - calidad liviana", "rtsp://USUARIO:CLAVE@IP:554/stream2"),
    ("Otra marca (la ruta final va en su manual)", "rtsp://USUARIO:CLAVE@IP:554/stream1"),
]
MARCADORES_MODELO = ("USUARIO", "CLAVE", "@IP:")


def boton_copiar(campo):
    """Boton chico con icono de copiar que pone el texto de `campo` en el portapapeles."""
    boton = QPushButton(" Copiar")
    boton.setIcon(icono("copiar", "#e7e9ee", 16))
    boton.setIconSize(QSize(16, 16))
    boton.setToolTip("Copiar al portapapeles")

    def copiar():
        if not campo.text().strip():
            return
        QApplication.clipboard().setText(campo.text().strip())
        boton.setText(" Copiado")
        QTimer.singleShot(1500, lambda: boton.setText(" Copiar"))

    boton.clicked.connect(copiar)
    return boton


class CamarasView(QWidget):
    """Alta de camaras sueltas (sin DVR/NVR): IP de cualquier marca por
    RTSP, o la webcam USB de la PC."""

    agregar_solicitado = pyqtSignal(dict)
    quitar_solicitado = pyqtSignal(int)
    refrescar_solicitado = pyqtSignal()
    probar_solicitado = pyqtSignal(dict)
    detectar_usb_solicitado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._permitido_quitar = False
        layout = QVBoxLayout(self)

        grupo = QGroupBox("Agregar una camara suelta (para un DVR/NVR use la pestana \"NVR / DVR\")")
        formulario = QFormLayout(grupo)
        self.layout_formulario = formulario

        self.campo_nombre = QLineEdit()
        self.campo_nombre.setPlaceholderText("Ej: Puerta principal")
        formulario.addRow("Nombre:", self.campo_nombre)

        self.campo_tipo = QComboBox()
        self.campo_tipo.addItems([TIPO_IP, TIPO_USB])
        self.campo_tipo.currentTextChanged.connect(self._actualizar_tipo)
        formulario.addRow("Tipo:", self.campo_tipo)

        # ---- camara IP: con marca/IP/usuario/clave el enlace RTSP se arma solo ----
        self.bloque_ip = QWidget()
        form_ip = QFormLayout(self.bloque_ip)
        form_ip.setContentsMargins(0, 0, 0, 0)
        self.campo_marca = QComboBox()
        self.campo_marca.addItems(MARCAS_IP)
        form_ip.addRow("Marca:", self.campo_marca)
        self.campo_ip = QLineEdit()
        self.campo_ip.setPlaceholderText("Ej: 192.168.1.64")
        form_ip.addRow("IP:", self.campo_ip)
        self.campo_usuario = QLineEdit("admin")
        form_ip.addRow("Usuario:", self.campo_usuario)
        self.campo_clave = QLineEdit()
        self.campo_clave.setEchoMode(QLineEdit.EchoMode.Password)
        form_ip.addRow("Clave:", self.campo_clave)

        avanzado = QWidget()
        form_avanzado = QFormLayout(avanzado)
        form_avanzado.setContentsMargins(0, 0, 0, 0)
        self.campo_puerto = QLineEdit("554")
        form_avanzado.addRow("Puerto RTSP:", self.campo_puerto)
        self.campo_canal = QLineEdit("1")
        form_avanzado.addRow("Canal:", self.campo_canal)
        self.campo_flujo = QComboBox()
        self.campo_flujo.addItems(["Principal (mejor calidad)", "Secundario (mas liviano)"])
        form_avanzado.addRow("Calidad:", self.campo_flujo)
        self.chk_ptz = QCheckBox("Tiene motor PTZ (se puede mover)")
        form_avanzado.addRow(self.chk_ptz)
        form_ip.addRow(Desplegable("Opciones avanzadas", avanzado))
        formulario.addRow(self.bloque_ip)

        for campo in (self.campo_ip, self.campo_puerto, self.campo_usuario, self.campo_clave, self.campo_canal):
            campo.textChanged.connect(self._actualizar_url)
        self.campo_marca.currentTextChanged.connect(self._actualizar_url)
        self.campo_flujo.currentIndexChanged.connect(self._actualizar_url)

        # ---- webcam USB: el indice cambia de PC a PC, se detecta en vez de adivinar ----
        self.bloque_usb = QWidget()
        fila_usb = QHBoxLayout(self.bloque_usb)
        fila_usb.setContentsMargins(0, 0, 0, 0)
        self.btn_detectar_usb = QPushButton("Buscar webcams")
        self.btn_detectar_usb.clicked.connect(self.detectar_usb_solicitado.emit)
        fila_usb.addWidget(self.btn_detectar_usb)
        self.combo_usb_detectadas = QComboBox()
        self.combo_usb_detectadas.setPlaceholderText("(pulse Buscar webcams)")
        self.combo_usb_detectadas.currentIndexChanged.connect(self._elegir_usb_detectada)
        fila_usb.addWidget(self.combo_usb_detectadas, stretch=1)
        formulario.addRow(self.bloque_usb)

        fila_url = QHBoxLayout()
        self.campo_url = QLineEdit()
        fila_url.addWidget(self.campo_url, stretch=1)
        self.btn_copiar_url = boton_copiar(self.campo_url)
        fila_url.addWidget(self.btn_copiar_url)
        self.lbl_url = QLabel()
        formulario.addRow(self.lbl_url, fila_url)

        # ---- enlaces modelo por marca: copiarlos o pasarlos al campo de arriba ----
        self.bloque_modelos = QWidget()
        v_modelos = QVBoxLayout(self.bloque_modelos)
        v_modelos.setContentsMargins(0, 0, 0, 0)
        fila_modelo = QHBoxLayout()
        self.combo_modelo = QComboBox()
        for nombre, enlace in ENLACES_MODELO:
            self.combo_modelo.addItem(nombre, enlace)
        fila_modelo.addWidget(self.combo_modelo)
        self.campo_modelo = QLineEdit()
        self.campo_modelo.setReadOnly(True)
        fila_modelo.addWidget(self.campo_modelo, stretch=1)
        fila_modelo.addWidget(boton_copiar(self.campo_modelo))
        btn_usar_modelo = QPushButton("Usar y editar")
        btn_usar_modelo.setToolTip("Pasa este enlace al campo \"Enlace RTSP\" para cambiar USUARIO, CLAVE e IP")
        btn_usar_modelo.clicked.connect(self._usar_enlace_modelo)
        fila_modelo.addWidget(btn_usar_modelo)
        v_modelos.addLayout(fila_modelo)
        ayuda_modelo = QLabel("Cambie USUARIO, CLAVE e IP por los de su camara. Para el canal 2 de un grabador: 201 / channel=2.")
        ayuda_modelo.setStyleSheet("color: #9aa6b3; font-size: 11px;")
        v_modelos.addWidget(ayuda_modelo)
        self.combo_modelo.currentIndexChanged.connect(
            lambda _i: self.campo_modelo.setText(self.combo_modelo.currentData())
        )
        self.campo_modelo.setText(self.combo_modelo.currentData())
        formulario.addRow("Enlaces modelo:", self.bloque_modelos)

        fila_botones = QHBoxLayout()
        self.btn_probar = QPushButton("Probar conexion")
        self.btn_probar.clicked.connect(self._emitir_probar)
        fila_botones.addWidget(self.btn_probar)
        self.btn_agregar = QPushButton("Agregar camara")
        self.btn_agregar.setStyleSheet("QPushButton { background: #1f8f86; font-weight: bold; }")
        self.btn_agregar.clicked.connect(self._emitir_agregar)
        fila_botones.addWidget(self.btn_agregar)
        formulario.addRow(fila_botones)

        layout.addWidget(grupo)
        self._actualizar_tipo()

        encabezado = QHBoxLayout()
        encabezado.addWidget(QLabel("Camaras registradas"))
        encabezado.addStretch()
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

    # ---------------- formulario ----------------
    def _es_usb(self):
        return self.campo_tipo.currentText() == TIPO_USB

    def _actualizar_tipo(self):
        usb = self._es_usb()
        self.bloque_ip.setVisible(not usb)
        self.bloque_usb.setVisible(usb)
        self.btn_copiar_url.setVisible(not usb)
        self.bloque_modelos.setVisible(not usb)
        etiqueta_modelos = self.layout_formulario.labelForField(self.bloque_modelos)
        if etiqueta_modelos:
            etiqueta_modelos.setVisible(not usb)
        self.campo_url.clear()
        if usb:
            self.lbl_url.setText("Indice USB:")
            self.campo_url.setPlaceholderText("0 (normalmente). Pulse \"Buscar webcams\"")
        else:
            self.lbl_url.setText("Enlace RTSP:")
            self.campo_url.setPlaceholderText("Se arma solo con la IP, usuario y clave")
            self._actualizar_url()

    def _actualizar_url(self):
        if self._es_usb():
            return
        url = construir_url_canal(
            self.campo_marca.currentText(),
            self.campo_ip.text().strip(),
            self.campo_puerto.text().strip(),
            self.campo_usuario.text().strip(),
            self.campo_clave.text(),
            self.campo_canal.text().strip(),
            self.campo_flujo.currentIndex() == 0,
        )
        if url:
            self.campo_url.setText(url)

    def _usar_enlace_modelo(self):
        enlace = self.combo_modelo.currentData()
        self.campo_url.setText(enlace)
        self.campo_url.setFocus()
        # deja seleccionado "USUARIO": se escribe encima directamente
        inicio = enlace.find("USUARIO")
        self.campo_url.setSelection(inicio, len("USUARIO"))

    def set_detectando_usb(self, activo):
        self.btn_detectar_usb.setEnabled(not activo)
        self.btn_detectar_usb.setText("Buscando..." if activo else "Buscar webcams")

    def mostrar_camaras_usb_detectadas(self, encontradas):
        self.combo_usb_detectadas.clear()
        if not encontradas:
            self.combo_usb_detectadas.addItem("Ninguna webcam respondio", None)
            QMessageBox.warning(
                self, "Buscar webcams",
                "No se encontro ninguna webcam en los indices 0 a 4. Verifique que este "
                "conectada y que ninguna otra app (Zoom, Teams...) la este usando.",
            )
            return
        for c in encontradas:
            self.combo_usb_detectadas.addItem(f"Webcam {c['indice']} ({c['resolucion']})", c["indice"])

    def _elegir_usb_detectada(self, _posicion):
        indice = self.combo_usb_detectadas.currentData()
        if indice is not None:
            self.campo_url.setText(str(indice))

    def _url_tiene_credenciales_de_ejemplo(self, url):
        return "rtsp://usuario:clave@" in url or "rtsp://:" in url or ":@" in url

    def _validar_url(self, url, verbo):
        if not url:
            QMessageBox.warning(self, "Falta un dato", "Complete la IP (o elija la webcam) antes de " + verbo + ".")
            return False
        if not self._es_usb() and any(m in url for m in MARCADORES_MODELO):
            QMessageBox.warning(
                self, "Falta completar el enlace",
                "El enlace todavia dice USUARIO, CLAVE o IP: cambielos por los datos reales de su camara.",
            )
            return False
        if not self._es_usb() and self._url_tiene_credenciales_de_ejemplo(url):
            QMessageBox.warning(
                self, "Falta usuario o clave",
                "Escriba el usuario y la clave reales de la camara (si no, la camara rechaza la conexion).",
            )
            return False
        return True

    def _emitir_probar(self):
        url = self.campo_url.text().strip()
        if self._validar_url(url, "probar"):
            self.probar_solicitado.emit({"tipo_conexion": "USB" if self._es_usb() else "RTSP", "url": url})

    def set_probando(self, activo):
        self.btn_probar.setEnabled(not activo)
        self.btn_probar.setText("Probando..." if activo else "Probar conexion")

    def prellenar_desde_radar(self, info):
        """Desde el "Radar de camaras" ("Usar en Camaras"): completa lo que ya
        se sabe (marca, IP y, si se escribieron en el Radar, usuario/clave)."""
        self.campo_tipo.setCurrentText(TIPO_IP)
        marca = info.get("marca_app", "Generico")
        self.campo_marca.setCurrentText(marca if marca in MARCAS_IP else "Generico")
        self.campo_ip.setText(info.get("ip", ""))
        if info.get("usuario"):
            self.campo_usuario.setText(info["usuario"])
        if info.get("clave"):
            self.campo_clave.setText(info["clave"])
        self.campo_nombre.setFocus()

    def _emitir_agregar(self):
        nombre = self.campo_nombre.text().strip()
        url = self.campo_url.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Falta el nombre", "Escriba un nombre para la camara (ej. Puerta principal).")
            self.campo_nombre.setFocus()
            return
        if not self._validar_url(url, "agregar"):
            return
        usb = self._es_usb()
        self.agregar_solicitado.emit({
            "nombre": nombre,
            "marca": "WebcamUSB" if usb else self.campo_marca.currentText(),
            "tipo_conexion": "USB" if usb else "RTSP",
            "url": url,
            "tiene_ptz": not usb and self.chk_ptz.isChecked(),
        })

    def limpiar_formulario(self):
        self.campo_nombre.clear()
        self.campo_ip.clear()
        self.campo_clave.clear()
        self.chk_ptz.setChecked(False)
        self._actualizar_tipo()

    # ---------------- tabla ----------------
    def _emitir_quitar(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            QMessageBox.information(self, "Quitar camara", "Seleccione una camara de la tabla primero.")
            return
        self.quitar_solicitado.emit(int(self.tabla.item(filas[0].row(), 0).text()))

    def _actualizar_boton_quitar(self):
        # currentRow() no se resetea al deseleccionar: hasSelection() si
        self.btn_quitar.setEnabled(self._permitido_quitar and self.tabla.selectionModel().hasSelection())

    def permitir_quitar(self, permitido):
        self._permitido_quitar = permitido
        self.btn_quitar.setVisible(permitido)
        self._actualizar_boton_quitar()

    def cargar(self, camaras):
        self.tabla.setRowCount(0)
        for fila, c in enumerate(camaras):
            self.tabla.insertRow(fila)
            grupo = f"{c.get('DispositivoTipo') or 'DVR'} {c['Dispositivo']}" if c.get("Dispositivo") else "Independiente"
            valores = [
                c["IdCamara"], c["Nombre"], grupo, c["Marca"],
                c["TipoConexion"], c["UrlConexion"], c["Estado"],
                "Si" if c.get("TienePTZ") else "No",
            ]
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
