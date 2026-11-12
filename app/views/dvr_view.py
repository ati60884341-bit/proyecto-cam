from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QTextEdit, QScrollArea, QButtonGroup,
)

from app.services import network_info
from app.views.UI.panel_mi_red import PanelMiRed
from app.views.UI.checklist_red_dialog import ChecklistRedDialog
from app.views.UI.desplegable import Desplegable

MARCAS_DVR = ["Hikvision", "Dahua"]
COLUMNAS = ["ID", "Tipo", "Nombre", "Marca", "IP", "En esta red", "Canales", "Camaras activas"]
ESTILO_TIPO = (
    "QPushButton { padding: 10px 18px; font-weight: bold; }"
    "QPushButton:checked { background: #1f8f86; border-color: #36d6c9; color: white; }"
)


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
    usar_perfil_solicitado = pyqtSignal(int)
    guardar_perfil_solicitado = pyqtSignal(dict)
    agregar_nota_solicitada = pyqtSignal(int, str)
    fila_dvr_seleccionada = pyqtSignal(object)  # id_dispositivo o None
    primera_vez_visible = pyqtSignal()  # dispara el checklist de red (una vez por sesion)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._permitido_quitar = False
        self._ya_se_mostro = False

        # Esta pestana crecio bastante (perfiles de sitio, tabla, bitacora,
        # registro) y ya no entra completa en una laptop con pantalla chica
        # (ej. 1366x768): todo el contenido va dentro de un QScrollArea en
        # vez de directo en self, para que se pueda bajar con el mouse en
        # vez de quedar amontonado/cortado.
        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        contenido = QWidget()
        scroll.setWidget(contenido)
        layout_externo.addWidget(scroll)
        layout = QVBoxLayout(contenido)

        intro = QLabel("Registre el grabador una vez: el programa busca solo todas sus camaras.")
        intro.setStyleSheet("color: #9aa6b3;")
        layout.addWidget(intro)

        # ---------------- perfiles de sitio (dentro de "Herramientas") ----------------
        grupo_perfiles = QWidget()
        v_perfiles = QVBoxLayout(grupo_perfiles)
        v_perfiles.setContentsMargins(0, 0, 0, 0)
        v_perfiles.addWidget(QLabel("Perfil de sitio: precarga los datos de un lugar donde ya se instalo (sin la clave)."))
        fila_elegir = QHBoxLayout()
        self.combo_perfiles = QComboBox()
        self.combo_perfiles.addItem("— Elegir perfil guardado —", None)
        fila_elegir.addWidget(self.combo_perfiles, stretch=1)
        btn_usar_perfil = QPushButton("Usar este perfil")
        btn_usar_perfil.clicked.connect(self._emitir_usar_perfil)
        fila_elegir.addWidget(btn_usar_perfil)
        v_perfiles.addLayout(fila_elegir)

        fila_guardar = QHBoxLayout()
        self.campo_nombre_perfil = QLineEdit()
        self.campo_nombre_perfil.setPlaceholderText("Nombre del sitio, ej: Taller Los Olivos")
        fila_guardar.addWidget(self.campo_nombre_perfil, stretch=1)
        self.campo_red_router = QLineEdit()
        self.campo_red_router.setPlaceholderText("Nombre de la red del router portatil (opcional)")
        fila_guardar.addWidget(self.campo_red_router, stretch=1)
        btn_guardar_perfil = QPushButton("Guardar datos del formulario como perfil")
        btn_guardar_perfil.clicked.connect(self._emitir_guardar_perfil)
        fila_guardar.addWidget(btn_guardar_perfil)
        v_perfiles.addLayout(fila_guardar)

        herramientas = QWidget()
        v_herramientas = QVBoxLayout(herramientas)
        v_herramientas.setContentsMargins(0, 0, 0, 0)
        v_herramientas.addWidget(PanelMiRed())
        v_herramientas.addWidget(grupo_perfiles)

        grupo = QGroupBox("Agregar un grabador")
        formulario = QFormLayout(grupo)

        # DVR / NVR: dos botones grandes en vez de una lista
        fila_tipo = QHBoxLayout()
        self.grupo_tipo = QButtonGroup(self)
        for indice, (tipo, ayuda) in enumerate((
            ("DVR", "Camaras analogicas (cable coaxial)"),
            ("NVR", "Camaras IP (cable de red / WiFi)"),
        )):
            boton = QPushButton(f"{tipo}\n{ayuda}")
            boton.setCheckable(True)
            boton.setStyleSheet(ESTILO_TIPO)
            boton.setProperty("tipo", tipo)
            self.grupo_tipo.addButton(boton, indice)
            fila_tipo.addWidget(boton)
        self.grupo_tipo.button(0).setChecked(True)
        formulario.addRow("Tipo:", fila_tipo)

        self.campo_nombre = QLineEdit()
        self.campo_nombre.setPlaceholderText("Ej: Patio Central")
        formulario.addRow("Nombre:", self.campo_nombre)

        self.campo_marca = QComboBox()
        self.campo_marca.addItems(MARCAS_DVR)
        formulario.addRow("Marca:", self.campo_marca)

        self.campo_ip = QLineEdit()
        self.campo_ip.setPlaceholderText("Ej: 192.168.1.64")
        formulario.addRow("IP:", self.campo_ip)

        self.campo_usuario = QLineEdit("admin")
        formulario.addRow("Usuario:", self.campo_usuario)

        self.campo_clave = QLineEdit()
        self.campo_clave.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_clave.setPlaceholderText("La misma con que entra al menu del grabador")
        formulario.addRow("Clave:", self.campo_clave)

        self.campo_canales = QComboBox()
        self.campo_canales.setEditable(True)
        self.campo_canales.addItems(["4", "8", "16", "32"])
        formulario.addRow("Canales:", self.campo_canales)

        avanzado = QWidget()
        form_avanzado = QFormLayout(avanzado)
        form_avanzado.setContentsMargins(0, 0, 0, 0)
        self.campo_puerto = QLineEdit("554")
        form_avanzado.addRow("Puerto RTSP:", self.campo_puerto)
        self.chk_ptz = QCheckBox("Todas sus camaras tienen motor PTZ (se pueden mover)")
        form_avanzado.addRow(self.chk_ptz)
        formulario.addRow(Desplegable("Opciones avanzadas", avanzado))

        self.btn_registrar = QPushButton("Agregar y buscar sus camaras")
        self.btn_registrar.setStyleSheet("QPushButton { background: #1f8f86; font-weight: bold; }")
        self.btn_registrar.clicked.connect(self._emitir_registrar)
        formulario.addRow(self.btn_registrar)

        self.lbl_progreso = QLabel("")
        formulario.addRow(self.lbl_progreso)

        layout.addWidget(grupo)
        layout.addWidget(Desplegable("Herramientas de instalacion (red de esta PC, perfiles de sitio)", herramientas))

        encabezado = QHBoxLayout()
        encabezado.addWidget(QLabel("Grabadores (DVR/NVR) registrados"))
        encabezado.addStretch()

        # a diferencia de "Quitar grabador", esto no borra ni desactiva nada:
        # cualquier usuario puede usarlo (igual que "Agregar camara" en la
        # pestana Camaras), no solo Administrador
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

        # ---------------- bitacora de instalacion (compartida) ----------------
        grupo_bitacora = QWidget()
        v_bitacora = QVBoxLayout(grupo_bitacora)
        v_bitacora.setContentsMargins(0, 0, 0, 0)
        v_bitacora.addWidget(QLabel("Notas del grabador seleccionado arriba; las ve todo el equipo."))
        self.texto_bitacora = QTextEdit()
        self.texto_bitacora.setReadOnly(True)
        self.texto_bitacora.setMaximumHeight(90)
        v_bitacora.addWidget(self.texto_bitacora)

        fila_nota = QHBoxLayout()
        self.campo_nota = QLineEdit()
        self.campo_nota.setPlaceholderText("Nueva nota para este grabador...")
        fila_nota.addWidget(self.campo_nota, stretch=1)
        self.btn_agregar_nota = QPushButton("Agregar nota")
        self.btn_agregar_nota.setEnabled(False)
        self.btn_agregar_nota.clicked.connect(self._emitir_agregar_nota)
        fila_nota.addWidget(self.btn_agregar_nota)
        v_bitacora.addLayout(fila_nota)

        layout.addWidget(Desplegable("Bitacora de instalacion (notas del equipo)", grupo_bitacora))

        layout.addWidget(QLabel("Resultado de la busqueda de camaras:"))
        self.texto_log = QTextEdit()
        self.texto_log.setReadOnly(True)
        self.texto_log.setMaximumHeight(140)
        layout.addWidget(self.texto_log)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._ya_se_mostro:
            self._ya_se_mostro = True
            self.primera_vez_visible.emit()

    def mostrar_checklist_red(self):
        ChecklistRedDialog(self).exec()

    def prellenar_desde_radar(self, info):
        """Llamado desde el "Radar de camaras" al elegir "Usar en NVR/DVR"
        para un hallazgo: completa marca/IP/cantidad de canales con lo que
        se detecto (real para marca e IP; la cantidad de canales es una
        ESTIMACION por fuentes de video ONVIF) - el usuario confirma y
        completa usuario/clave antes de registrar (o las precarga si ya se
        escribieron en el Radar, ej. para el "Reintentar con estas
        credenciales")."""
        marca = info.get("marca_app", "Hikvision")
        if marca in MARCAS_DVR:
            self.campo_marca.setCurrentText(marca)
        self.campo_ip.setText(info.get("ip", ""))
        canales = info.get("canales_detectados", 1)
        if canales > 1:
            self.campo_canales.setCurrentText(str(canales))
        if "NVR" in (info.get("modelo") or "").upper():
            self.grupo_tipo.button(1).setChecked(True)
        if not self.campo_nombre.text().strip():
            modelo = info.get("modelo", "")
            self.campo_nombre.setText(f"{marca} {modelo}".strip() or f"Grabador {info.get('ip', '')}")
        if info.get("usuario"):
            self.campo_usuario.setText(info["usuario"])
        if info.get("clave"):
            self.campo_clave.setText(info["clave"])
        self.campo_usuario.setFocus()

    # ---------------- perfiles de sitio ----------------
    def cargar_perfiles(self, perfiles):
        self.combo_perfiles.blockSignals(True)
        self.combo_perfiles.clear()
        self.combo_perfiles.addItem("— Elegir perfil guardado —", None)
        for p in perfiles:
            self.combo_perfiles.addItem(p["Nombre"], p["IdPerfil"])
        self.combo_perfiles.blockSignals(False)

    def _emitir_usar_perfil(self):
        id_perfil = self.combo_perfiles.currentData()
        if id_perfil is None:
            QMessageBox.information(self, "Perfil de sitio", "Elige un perfil de la lista primero.")
            return
        self.usar_perfil_solicitado.emit(id_perfil)

    def aplicar_perfil(self, perfil):
        if perfil.get("MarcaTipica") in MARCAS_DVR:
            self.campo_marca.setCurrentText(perfil["MarcaTipica"])
        if perfil.get("IpDvrTipica"):
            self.campo_ip.setText(perfil["IpDvrTipica"])
        if perfil.get("PuertoTipico"):
            self.campo_puerto.setText(str(perfil["PuertoTipico"]))
        if perfil.get("UsuarioTipico"):
            self.campo_usuario.setText(perfil["UsuarioTipico"])
        self.campo_clave.setFocus()

    def _emitir_guardar_perfil(self):
        nombre = self.campo_nombre_perfil.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Falta el nombre", "Escribe un nombre para el perfil (ej. el nombre del taller).")
            return
        self.guardar_perfil_solicitado.emit({
            "nombre": nombre,
            "ip_dvr_tipica": self.campo_ip.text().strip(),
            "puerto_tipico": self.campo_puerto.text().strip() or "554",
            "marca_tipica": self.campo_marca.currentText(),
            "usuario_tipico": self.campo_usuario.text().strip() or "admin",
            "nombre_red_router": self.campo_red_router.text().strip(),
            "notas": "",
        })

    def perfil_guardado(self, nombre):
        self.campo_nombre_perfil.clear()
        QMessageBox.information(self, "Perfil guardado", f"Perfil \"{nombre}\" guardado. Ya aparece en la lista.")

    # ---------------- registrar + detectar ----------------
    def _emitir_registrar(self):
        nombre = self.campo_nombre.text().strip()
        ip = self.campo_ip.text().strip()
        if not nombre or not ip:
            QMessageBox.warning(self, "Faltan datos", "Complete el nombre y la IP del grabador.")
            return
        try:
            cantidad_canales = int(self.campo_canales.currentText().strip() or "4")
        except ValueError:
            QMessageBox.warning(self, "Dato invalido", "La cantidad de canales debe ser un numero.")
            return
        if cantidad_canales < 1 or cantidad_canales > 64:
            QMessageBox.warning(self, "Dato invalido", "La cantidad de canales debe estar entre 1 y 64.")
            return
        if not self.campo_clave.text():
            # Hikvision/Dahua activados nunca aceptan clave vacia: sin esto se
            # registraba igual y la deteccion fallaba con un generico "revise
            # IP/usuario/clave" que no decia que la clave faltaba
            QMessageBox.warning(
                self, "Falta la clave",
                "Escriba la clave del grabador (la misma con que entra al menu del DVR "
                "o a su pagina web). Sin clave el DVR rechaza la conexion.",
            )
            self.campo_clave.setFocus()
            return
        self.registrar_solicitado.emit({
            "tipo": self.grupo_tipo.checkedButton().property("tipo"),
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
        self.btn_detectar_nuevos.setEnabled(not activo and self.tabla.selectionModel().hasSelection())
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
        nombre = self.tabla.item(fila, 2).text()
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
        self.btn_detectar_nuevos.setEnabled(hay_seleccion)
        self.btn_agregar_nota.setEnabled(hay_seleccion)
        self.fila_dvr_seleccionada.emit(self._id_seleccionado())

    def permitir_quitar(self, permitido):
        self._permitido_quitar = permitido
        self.btn_quitar.setVisible(permitido)
        self._actualizar_botones_fila()

    def cargar(self, dispositivos):
        self.tabla.setRowCount(0)
        interfaces = network_info.listar_interfaces_red()
        for fila, d in enumerate(dispositivos):
            self.tabla.insertRow(fila)
            en_red = network_info.ip_en_red_local(d["IP"], interfaces)
            en_red_texto = {True: "Si", False: "No — otra subred"}.get(en_red, "?")
            valores = [
                d["IdDispositivo"], d["Tipo"], d["Nombre"], d["Marca"], d["IP"], en_red_texto,
                d["CantidadCanales"], d["CamarasActivas"],
            ]
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                if columna == 5 and en_red is False:
                    item.setForeground(QColor("#e35b5b"))
                self.tabla.setItem(fila, columna, item)

    # ---------------- bitacora de instalacion ----------------
    def mostrar_bitacora(self, notas):
        if not notas:
            self.texto_bitacora.setPlainText("(sin notas todavia para este grabador)")
            return
        lineas = [
            f"[{n['Fecha']}] {n.get('NombreCompleto') or 'alguien del equipo'}: {n['Texto']}"
            for n in notas
        ]
        self.texto_bitacora.setPlainText("\n".join(lineas))

    def limpiar_bitacora(self):
        self.texto_bitacora.setPlainText("(selecciona un grabador arriba)")

    def _emitir_agregar_nota(self):
        id_dispositivo = self._id_seleccionado()
        texto = self.campo_nota.text().strip()
        if id_dispositivo is None or not texto:
            return
        self.agregar_nota_solicitada.emit(id_dispositivo, texto)
        self.campo_nota.clear()
