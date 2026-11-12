from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox, QPushButton,
    QMessageBox, QScrollArea, QFrame,
)

from app.views.UI.desplegable import Desplegable
from app.views.UI.iconos import icono, pixmap_icono
from app.views.UI.panel_mi_red import PanelMiRed
from app.views.UI.radar_animado import RadarAnimado

ESTILO_TARJETA = (
    "QFrame#tarjetaRadar { background: rgba(23, 27, 36, 230); border: 1px solid #2a303c; border-radius: 10px; }"
)
ESTILO_BOTON_BUSCAR = (
    "QPushButton { background: #1f8f86; color: white; font-weight: bold; font-size: 14px;"
    " padding: 10px 26px; border-radius: 10px; }"
    "QPushButton:hover { background: #26a89e; }"
)


def _es_grabador(info):
    return info.get("canales_detectados", 1) > 1


class TarjetaEquipo(QFrame):
    """Un equipo encontrado: icono, que es, su IP y botones directos."""

    def __init__(self, info, al_usar_camara, al_usar_grabador, al_reintentar, parent=None):
        super().__init__(parent)
        self.setObjectName("tarjetaRadar")
        self.setStyleSheet(ESTILO_TARJETA)
        fila = QHBoxLayout(self)

        icono_lbl = QLabel()
        icono_lbl.setPixmap(pixmap_icono("dvr" if _es_grabador(info) else "camaras", "#36d6c9", 34))
        icono_lbl.setFixedSize(42, 42)
        icono_lbl.setStyleSheet("border: none;")
        fila.addWidget(icono_lbl)

        desconocida = info["marca"] == "Desconocida"
        titulo = "Equipo sin identificar" if desconocida else f"{info['marca']} {info['modelo']}".strip()
        if _es_grabador(info):
            que_es = f"Grabador con {info['canales_detectados']} canales"
        elif desconocida:
            que_es = "Pide usuario y clave para identificarse"
        else:
            que_es = "Camara"
        textos = QVBoxLayout()
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet("font-weight: bold; font-size: 13px; border: none;")
        textos.addWidget(lbl_titulo)
        lbl_detalle = QLabel(f"{info['ip']}  ·  {que_es}")
        lbl_detalle.setStyleSheet("color: #9aa6b3; border: none;")
        textos.addWidget(lbl_detalle)
        self.setToolTip(
            f"Encontrado por: {info.get('metodo')}\nPuerto ONVIF: {info.get('puerto_onvif') or '-'}\n"
            f"Firmware: {info.get('firmware') or '-'}\nN.º de serie: {info.get('numero_serie') or '-'}"
        )
        fila.addLayout(textos, stretch=1)

        if desconocida:
            btn_reintentar = QPushButton(" Probar con usuario/clave")
            btn_reintentar.setToolTip("Usa el usuario y la clave de \"Opciones\" (arriba) solo para este equipo")
            btn_reintentar.clicked.connect(al_reintentar)
            fila.addWidget(btn_reintentar)
        btn_camara = QPushButton(" Agregar como camara")
        btn_camara.setIcon(icono("camaras", "#e7e9ee", 16))
        btn_camara.setIconSize(QSize(16, 16))
        btn_camara.clicked.connect(al_usar_camara)
        btn_grabador = QPushButton(" Agregar como DVR/NVR")
        btn_grabador.setIcon(icono("dvr", "#e7e9ee", 16))
        btn_grabador.setIconSize(QSize(16, 16))
        btn_grabador.clicked.connect(al_usar_grabador)
        # el boton que probablemente corresponde va resaltado
        recomendado = btn_grabador if _es_grabador(info) else btn_camara
        recomendado.setStyleSheet("QPushButton { background: #1f8f86; color: white; }")
        fila.addWidget(btn_camara)
        fila.addWidget(btn_grabador)


class RadarView(QWidget):
    """Pestana "Radar de camaras": busca solo las camaras y grabadores de la
    red (sin saber su IP), como SADP de Hikvision o ConfigTool de Dahua.
    La marca/modelo son reales (el equipo se identifica via ONVIF); si es
    camara o grabador es una estimacion por cantidad de canales."""

    escanear_solicitado = pyqtSignal(dict)  # {escaneo_completo, usuario, clave}
    reintentar_solicitado = pyqtSignal(dict)  # {ip, usuario, clave}
    usar_en_camaras_solicitado = pyqtSignal(dict)
    usar_en_dvr_solicitado = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dispositivos = {}  # ip -> info, en orden de llegada
        self._escaneando = False

        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        contenido = QWidget()
        scroll.setWidget(contenido)
        externo.addWidget(scroll)
        layout = QVBoxLayout(contenido)

        encabezado = QHBoxLayout()
        icono_titulo = QLabel()
        icono_titulo.setPixmap(pixmap_icono("radar", "#36d6c9", 30))
        encabezado.addWidget(icono_titulo)
        titulos = QVBoxLayout()
        titulo = QLabel("Radar de camaras")
        titulo.setStyleSheet("font-size: 18px; font-weight: bold;")
        titulos.addWidget(titulo)
        subtitulo = QLabel("Encuentra las camaras y grabadores conectados a esta red. No hace falta saber su IP.")
        subtitulo.setStyleSheet("color: #9aa6b3;")
        titulos.addWidget(subtitulo)
        encabezado.addLayout(titulos, stretch=1)
        layout.addLayout(encabezado)

        self.radar = RadarAnimado()
        layout.addWidget(self.radar)

        self.lbl_progreso = QLabel("Pulse \"Buscar camaras\" para empezar.")
        self.lbl_progreso.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_progreso.setStyleSheet("color: #9aa6b3;")
        layout.addWidget(self.lbl_progreso)

        self.btn_escanear = QPushButton(" Buscar camaras")
        self.btn_escanear.setIcon(icono("radar", "#ffffff", 20))
        self.btn_escanear.setIconSize(QSize(20, 20))
        self.btn_escanear.setStyleSheet(ESTILO_BOTON_BUSCAR)
        self.btn_escanear.clicked.connect(self._emitir_escanear)
        layout.addWidget(self.btn_escanear, alignment=Qt.AlignmentFlag.AlignHCenter)

        opciones = QWidget()
        v_opciones = QVBoxLayout(opciones)
        v_opciones.setContentsMargins(0, 0, 0, 0)
        self.chk_completo = QCheckBox("Busqueda profunda: revisa toda la red (hasta 1 minuto)")
        self.chk_completo.setToolTip(
            "Ademas de la busqueda rapida (ONVIF, unos segundos), prueba las 254 direcciones\n"
            "de la red por el puerto de video 554: encuentra equipos con ONVIF apagado."
        )
        v_opciones.addWidget(self.chk_completo)
        fila_credenciales = QHBoxLayout()
        fila_credenciales.addWidget(QLabel("Usuario:"))
        self.campo_usuario = QLineEdit()
        self.campo_usuario.setPlaceholderText("admin")
        fila_credenciales.addWidget(self.campo_usuario)
        fila_credenciales.addWidget(QLabel("Clave:"))
        self.campo_clave = QLineEdit()
        self.campo_clave.setEchoMode(QLineEdit.EchoMode.Password)
        fila_credenciales.addWidget(self.campo_clave)
        v_opciones.addLayout(fila_credenciales)
        ayuda = QLabel("Opcional. Algunas camaras (ej. Tapo) solo dicen su marca si se les da usuario y clave.")
        ayuda.setStyleSheet("color: #9aa6b3; font-size: 11px;")
        v_opciones.addWidget(ayuda)
        v_opciones.addWidget(PanelMiRed())
        layout.addWidget(Desplegable("Opciones (busqueda profunda, usuario/clave, red de esta PC)", opciones))

        self.lbl_resultados = QLabel()
        self.lbl_resultados.setStyleSheet("font-weight: bold; font-size: 14px; color: #7fd6e8;")
        layout.addWidget(self.lbl_resultados)
        self.lista = QVBoxLayout()
        layout.addLayout(self.lista)
        layout.addStretch(1)

    # ---------------- escaneo ----------------
    def _emitir_escanear(self):
        self._dispositivos = {}
        self._limpiar_tarjetas()
        self.lbl_resultados.setText("")
        self.escanear_solicitado.emit({
            "escaneo_completo": self.chk_completo.isChecked(),
            "usuario": self.campo_usuario.text().strip() or "admin",
            "clave": self.campo_clave.text(),
        })

    def set_escaneando(self, activo):
        self._escaneando = activo
        self.btn_escanear.setEnabled(not activo)
        self.chk_completo.setEnabled(not activo)
        self.btn_escanear.setText(" Buscando..." if activo else " Buscar de nuevo")
        if activo:
            self.radar.iniciar()
        else:
            self.radar.detener()
            self._mostrar_resultados()

    def actualizar_progreso(self, texto):
        self.lbl_progreso.setText(texto)

    def agregar_dispositivo(self, info):
        """Llega uno por hallazgo, mientras se busca (o al reintentar una IP
        con usuario/clave: reemplaza su tarjeta en vez de duplicarla)."""
        self._dispositivos[info["ip"]] = info
        self.radar.agregar_punto(info["ip"])
        if self._escaneando:
            n = len(self._dispositivos)
            self.lbl_resultados.setText(f"{n} equipo{'s' if n != 1 else ''} encontrado{'s' if n != 1 else ''}...")
        else:
            self._mostrar_resultados()

    def _limpiar_tarjetas(self):
        while self.lista.count():
            widget = self.lista.takeAt(0).widget()
            if widget:
                widget.deleteLater()

    def _mostrar_resultados(self):
        self._limpiar_tarjetas()
        n = len(self._dispositivos)
        if not n:
            self.lbl_resultados.setText("No se encontro ningun equipo.")
            consejo = QLabel(
                "Revise que esta PC este en la misma red (WiFi o cable) que las camaras, "
                "o active la busqueda profunda en \"Opciones\"."
            )
            consejo.setWordWrap(True)
            consejo.setStyleSheet("color: #9aa6b3;")
            self.lista.addWidget(consejo)
            return
        self.lbl_resultados.setText(f"{n} equipo{'s' if n != 1 else ''} encontrado{'s' if n != 1 else ''}")
        for ip in self._dispositivos:
            self.lista.addWidget(TarjetaEquipo(
                self._dispositivos[ip],
                al_usar_camara=lambda _=False, i=ip: self._emitir_usar_en_camaras(i),
                al_usar_grabador=lambda _=False, i=ip: self._emitir_usar_en_dvr(i),
                al_reintentar=lambda _=False, i=ip: self._emitir_reintentar(i),
            ))

    # ---------------- acciones ----------------
    def _credenciales_escritas(self):
        """Usuario/clave escritos en Opciones: se llevan a "Camaras"/"NVR-DVR"
        para no tener que escribirlos dos veces."""
        return self.campo_usuario.text().strip(), self.campo_clave.text()

    def _emitir_usar_en_camaras(self, ip):
        usuario, clave = self._credenciales_escritas()
        self.usar_en_camaras_solicitado.emit(dict(self._dispositivos[ip], usuario=usuario, clave=clave))

    def _emitir_usar_en_dvr(self, ip):
        info = self._dispositivos[ip]
        if not _es_grabador(info):
            confirmacion = QMessageBox.question(
                self, "Confirmar",
                "Este equipo parece una camara suelta (1 sola fuente de video), no un grabador. "
                "¿Agregarlo como DVR/NVR de todas formas?",
            )
            if confirmacion != QMessageBox.StandardButton.Yes:
                return
        usuario, clave = self._credenciales_escritas()
        self.usar_en_dvr_solicitado.emit(dict(info, usuario=usuario, clave=clave))

    def _emitir_reintentar(self, ip):
        if not self.campo_clave.text():
            QMessageBox.information(
                self, "Falta la clave",
                "Abra \"Opciones\" (arriba), escriba el usuario y la clave de la camara y vuelva a probar.",
            )
            return
        self.reintentar_solicitado.emit({
            "ip": ip,
            "usuario": self.campo_usuario.text().strip() or "admin",
            "clave": self.campo_clave.text(),
        })
