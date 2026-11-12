from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QLineEdit, QTextEdit, QCheckBox, QComboBox, QDialog, QScrollArea,
)

from app.views.UI.zona_frame import ZonaFrame
from app.views.UI.grupo_grabador import GrupoGrabador
from app.views.UI.iconos import icono
from app.services.voice_service import listar_microfonos

ESTILO_BOTON_MICROFONO = (
    "QPushButton { background: #36d6c9; border: 3px solid #1f8f86; border-radius: 38px; padding: 0; }"
    "QPushButton:hover { background: #4fe3d7; }"
    "QPushButton:pressed { background: #e35b5b; border-color: #ff9a9a; }"
)

ESTILO_MANUAL = """
<style>
h2 { color: #36d6c9; margin-bottom: 4px; }
h3 { color: #7fd6e8; margin-top: 18px; margin-bottom: 6px; }
td { padding: 6px 10px; }
.di { color: #36d6c9; font-weight: bold; }
.gris { color: #9aa6b3; }
</style>
"""


def html_manual_comandos(camaras, numeros_ptz):
    """Manual corto: 3 pasos, las camaras con su numero y una tabla
    "quiero -> digo" con ejemplos de verdad (de las camaras que hay ahora).
    camaras: [(numero, nombre)]; numeros_ptz: numeros de las que tienen motor."""
    ejemplo = camaras[0][0] if camaras else 1
    filas_camaras = "".join(
        f"<tr><td class='di'>camara {n}</td><td>{nombre}</td></tr>" for n, nombre in camaras
    ) or "<tr><td class='gris'>(todavia no hay camaras)</td></tr>"
    acciones = [
        ("Verla en grande", f"camara {ejemplo} ampliar"),
        ("Acercar", f"camara {ejemplo} zoom"),
        ("Alejar", f"camara {ejemplo} alejar"),
        ("Quitar el zoom", f"camara {ejemplo} quitar zoom"),
        ("Sacar foto de evidencia", f"camara {ejemplo} foto"),
    ]
    if numeros_ptz:
        p = numeros_ptz[0]
        acciones += [
            ("Moverla (solo con motor)", f"camara {p} mover izquierda / derecha / arriba / abajo"),
            ("Guardar esa posicion", f"camara {p} preset 1 guardar"),
            ("Volver a esa posicion", f"camara {p} preset 1"),
        ]
    filas_acciones = "".join(f"<tr><td>{quiero}</td><td class='di'>{digo}</td></tr>" for quiero, digo in acciones)
    con_motor = (
        f"<p class='gris'>Con motor (se mueven): camara {', '.join(str(n) for n in numeros_ptz)}.</p>"
        if numeros_ptz else ""
    )
    return f"""{ESTILO_MANUAL}
<h2>Como hablarle al sistema</h2>
<table>
<tr><td><b>1.</b> Mantenga apretado el boton redondo del microfono</td></tr>
<tr><td><b>2.</b> Diga la camara y que quiere, ej. <span class='di'>camara {ejemplo} zoom</span></td></tr>
<tr><td><b>3.</b> Suelte el boton</td></tr>
</table>

<h3>Sus camaras</h3>
<p class='gris'>El numero es el del circulo en cada recuadro.</p>
<table>{filas_camaras}</table>

<h3>Que puede pedir</h3>
<table>
<tr><td class='gris'>Quiero...</td><td class='gris'>Digo...</td></tr>
{filas_acciones}
</table>
{con_motor}
<p class='gris'>Tambien puede escribir la misma frase en el cuadro de texto, sin microfono.</p>
"""


class DashboardView(QWidget):
    comando_manual_enviado = pyqtSignal(str)
    hablar_presionado = pyqtSignal()
    hablar_soltado = pyqtSignal()
    panico_manual = pyqtSignal()
    fatiga_confirmada = pyqtSignal()
    capturar_evidencia = pyqtSignal(str)
    ampliar_zona = pyqtSignal(str)
    reconectar_zona = pyqtSignal(str)
    deteccion_gesto_alternada = pyqtSignal(bool)
    alarma_silenciada = pyqtSignal()
    ocultar_zona = pyqtSignal(str)
    mostrar_zona = pyqtSignal(str)

    CLAVE_INDEPENDIENTES = "independientes"

    def __init__(self, camaras, parent=None):
        super().__init__(parent)
        self.zona_frames = {}
        self._columnas = 2
        self._zonas_con_ptz = []
        # un bloque por grabador (DVR/NVR) + uno para camaras independientes
        self._grupos = {}          # clave de grupo -> GrupoGrabador
        self._grupo_de_zona = {}   # clave de camara -> clave de grupo
        self._titulos_grabador = {}  # IdDispositivo -> titulo (se mejora al identificar DVR/NVR)
        self._numeros = {}           # numero dicho por voz -> clave de camara

        layout_raiz = QHBoxLayout(self)

        # -------- panel izquierdo: un recuadro por camara, agrupadas por grabador --------
        self.panel_zonas = QWidget()
        self.layout_grupos = QVBoxLayout(self.panel_zonas)
        self.layout_grupos.addStretch(1)
        for camara in camaras:
            self.agregar_zona_frame(camara)

        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setWidget(self.panel_zonas)
        layout_raiz.addWidget(desplazable, stretch=1)

        # -------- panel derecho: asistente de voz, panico, fatiga --------
        # con un ancho maximo fijo (no un "stretch" relativo al resto): sin
        # esto, en una ventana grande este panel terminaba ocupando casi la
        # mitad de la pantalla para solo un par de botones y un combo
        ANCHO_MAXIMO_PANEL_DERECHO = 360
        panel_derecho_widget = QWidget()
        panel_derecho_widget.setMaximumWidth(ANCHO_MAXIMO_PANEL_DERECHO)
        panel_derecho = QVBoxLayout(panel_derecho_widget)

        grupo_voz = QGroupBox("Asistente de comandos de voz")
        v = QVBoxLayout(grupo_voz)

        v.addWidget(QLabel("Microfono (elija el real si no reconoce bien):"))
        self.combo_microfono = QComboBox()
        self.combo_microfono.addItem("Microfono por defecto de Windows", None)
        for indice, nombre in listar_microfonos():
            self.combo_microfono.addItem(nombre, indice)
        v.addWidget(self.combo_microfono)

        # "mantener para hablar": graba mientras esta apretado, reconoce al soltar
        self.btn_hablar = QPushButton()
        self.btn_hablar.setFixedSize(76, 76)
        self.btn_hablar.setIcon(icono("microfono", "#06201d", 40))
        self.btn_hablar.setIconSize(QSize(40, 40))
        self.btn_hablar.setStyleSheet(ESTILO_BOTON_MICROFONO)
        self.btn_hablar.setToolTip('Mantenga apretado, diga por ej. "camara 1 zoom", y suelte')
        self.btn_hablar.pressed.connect(self.hablar_presionado.emit)
        self.btn_hablar.released.connect(self.hablar_soltado.emit)
        v.addSpacing(6)
        v.addWidget(self.btn_hablar, alignment=Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(6)
        self.lbl_estado_voz = QLabel("Mantenga apretado para hablar")
        self.lbl_estado_voz.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_estado_voz.setWordWrap(True)
        v.addWidget(self.lbl_estado_voz)
        # lo que se va entendiendo mientras se mantiene apretado
        self.lbl_voz_parcial = QLabel()
        self.lbl_voz_parcial.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_voz_parcial.setWordWrap(True)
        self.lbl_voz_parcial.setStyleSheet("color: #7fd6e8; font-size: 11px; font-style: italic;")
        v.addWidget(self.lbl_voz_parcial)

        fila_manual = QHBoxLayout()
        self.campo_comando = QLineEdit()
        self.campo_comando.setPlaceholderText('O escriba: "camara 1 ampliar"')
        fila_manual.addWidget(self.campo_comando)
        btn_enviar = QPushButton("Enviar")
        btn_enviar.clicked.connect(self._emitir_comando_manual)
        self.campo_comando.returnPressed.connect(self._emitir_comando_manual)
        fila_manual.addWidget(btn_enviar)
        v.addLayout(fila_manual)

        btn_manual = QPushButton("Ver manual de comandos")
        btn_manual.clicked.connect(self._mostrar_manual)
        v.addWidget(btn_manual)
        panel_derecho.addWidget(grupo_voz)

        # sirena de camara tapada: solo se habilita mientras esta sonando
        self.btn_silenciar_alarma = QPushButton("Silenciar alarma")
        self.btn_silenciar_alarma.setEnabled(False)
        self.btn_silenciar_alarma.clicked.connect(self.alarma_silenciada.emit)
        panel_derecho.addWidget(self.btn_silenciar_alarma)

        grupo_panico = QGroupBox("Modo panico silencioso")
        p = QVBoxLayout(grupo_panico)
        lbl_gesto = QLabel("Gesto: una o ambas manos arriba, 3 segundos, frente a la webcam.")
        lbl_gesto.setWordWrap(True)
        p.addWidget(lbl_gesto)
        self.chk_gesto = QCheckBox("Activar deteccion de gesto (usa mas CPU/RAM)")
        self.chk_gesto.toggled.connect(self.deteccion_gesto_alternada.emit)
        p.addWidget(self.chk_gesto)
        self.lbl_estado_gesto = QLabel("Deteccion de gesto: desactivada")
        p.addWidget(self.lbl_estado_gesto)
        self.btn_panico = QPushButton("Simular Modo Panico (manual)")
        self.btn_panico.setStyleSheet("background:#7a1f1f; color:white; font-weight:bold;")
        self.btn_panico.clicked.connect(self.panico_manual.emit)
        p.addWidget(self.btn_panico)
        panel_derecho.addWidget(grupo_panico)

        grupo_fatiga = QGroupBox("Auditor de fatiga (dead man's switch)")
        f = QVBoxLayout(grupo_fatiga)
        self.lbl_fatiga = QLabel("Sin solicitudes pendientes.")
        f.addWidget(self.lbl_fatiga)
        self.btn_confirmar = QPushButton("Confirmo que sigo atento")
        self.btn_confirmar.setEnabled(False)
        self.btn_confirmar.clicked.connect(self.fatiga_confirmada.emit)
        f.addWidget(self.btn_confirmar)
        self.set_boton_confirmar_urgente(False)
        panel_derecho.addWidget(grupo_fatiga)

        grupo_registro = QGroupBox("Bitacora de eventos")
        r = QVBoxLayout(grupo_registro)
        self.texto_log = QTextEdit()
        self.texto_log.setReadOnly(True)
        self.texto_log.setMinimumHeight(110)
        r.addWidget(self.texto_log)
        panel_derecho.addWidget(grupo_registro, stretch=1)

        # con desplazamiento: en pantallas bajas (laptop al 125%) Qt aplastaba
        # los grupos y el boton del microfono quedaba encima de su texto
        desplazable_derecho = QScrollArea()
        desplazable_derecho.setWidgetResizable(True)
        desplazable_derecho.setFrameShape(QScrollArea.Shape.NoFrame)
        desplazable_derecho.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        desplazable_derecho.setWidget(panel_derecho_widget)
        desplazable_derecho.setFixedWidth(ANCHO_MAXIMO_PANEL_DERECHO + 14)
        layout_raiz.addWidget(desplazable_derecho)

    # ---------------- grupos por grabador ----------------
    @staticmethod
    def titulo_grabador(camara, tipo=None, modelo=None):
        tipo = tipo or camara.get("DispositivoTipo") or "Grabador"
        detalle = " · ".join(x for x in (camara.get("DispositivoMarca"), modelo, camara.get("DispositivoIP")) if x)
        return f"{tipo} \"{camara.get('Dispositivo') or 'sin nombre'}\"" + (f"  —  {detalle}" if detalle else "")

    def _clave_grupo(self, camara):
        return camara.get("IdDispositivo") or self.CLAVE_INDEPENDIENTES

    def _obtener_grupo(self, camara):
        clave = self._clave_grupo(camara)
        grupo = self._grupos.get(clave)
        if grupo:
            return grupo
        if clave == self.CLAVE_INDEPENDIENTES:
            titulo = "Camaras independientes (webcam / IP sueltas)"
        else:
            titulo = self._titulos_grabador.get(clave) or self.titulo_grabador(camara)
        grupo = GrupoGrabador(titulo, self._columnas)
        grupo.mostrar_zona.connect(self.mostrar_zona.emit)
        self._grupos[clave] = grupo
        # independientes primero; los grabadores en orden de registro
        claves = sorted(self._grupos, key=lambda k: (k != self.CLAVE_INDEPENDIENTES, k if isinstance(k, int) else 0))
        self.layout_grupos.insertWidget(claves.index(clave), grupo)
        return grupo

    def actualizar_titulo_grabador(self, id_dispositivo, titulo):
        """El controlador lo llama al identificar si el equipo es DVR o NVR."""
        self._titulos_grabador[id_dispositivo] = titulo
        grupo = self._grupos.get(id_dispositivo)
        if grupo:
            grupo.set_titulo(titulo)

    # ---------------- camaras (un recuadro por camara) ----------------
    def _agregar_tile(self, camara):
        clave = camara["Clave"]
        zf = ZonaFrame(clave, camara["Nombre"])
        zf.capturar_evidencia.connect(self.capturar_evidencia.emit)
        zf.ampliar_zona.connect(self.ampliar_zona.emit)
        zf.reconectar_zona.connect(self.reconectar_zona.emit)
        zf.ocultar_zona.connect(self.ocultar_zona.emit)
        self._obtener_grupo(camara).agregar_tile(zf)
        self._grupo_de_zona[clave] = self._clave_grupo(camara)
        self.zona_frames[clave] = zf
        self._renumerar()
        return zf

    def agregar_zona_frame(self, camara):
        """Usado por el controlador al agregar una camara nueva (cualquier
        marca). Si la camara ya tenia recuadro en el MISMO grupo se reutiliza;
        si cambio de grabador (o es nueva) se crea en el grupo que corresponde."""
        clave = camara["Clave"]
        existente = self.zona_frames.get(clave)
        if existente and self._grupo_de_zona.get(clave) == self._clave_grupo(camara):
            existente.titulo.setText(camara["Nombre"])
            existente.video_label.setText("Conectando...")
            existente._set_botones_habilitados(True)
            self._grupos[self._clave_grupo(camara)].set_oculta(clave, False)
            return existente
        if existente:
            self.quitar_zona_frame(clave)
        return self._agregar_tile(camara)

    def _renumerar(self):
        """Numera las camaras en el orden en que se ven (de arriba a abajo):
        ese numero es el que se dice por voz ("camara 3 ampliar")."""
        self._numeros = {}
        numero = 0
        for i in range(self.layout_grupos.count()):
            grupo = self.layout_grupos.itemAt(i).widget()
            if not isinstance(grupo, GrupoGrabador):
                continue
            for tile in grupo.tiles():
                numero += 1
                tile.set_numero(numero)
                self._numeros[numero] = tile.nombre_zona

    def camaras_para_voz(self):
        """[(numero, clave)] de todas las camaras, en el orden de pantalla."""
        return sorted(self._numeros.items())

    def quitar_zona_frame(self, zona):
        """Borra el recuadro de la camara por completo del Centro de
        Monitoreo; si su grupo queda vacio (ej. se quito el grabador entero)
        el grupo tambien se va."""
        tile = self.zona_frames.pop(zona, None)
        clave = self._grupo_de_zona.pop(zona, None)
        grupo = self._grupos.get(clave)
        if tile and grupo:
            grupo.quitar_tile(tile)
        if tile:
            tile.setParent(None)
            tile.deleteLater()
        if grupo and grupo.cantidad() == 0:
            self._grupos.pop(clave, None)
            self.layout_grupos.removeWidget(grupo)
            grupo.setParent(None)
            grupo.deleteLater()
        self._renumerar()

    def set_zona_oculta(self, zona, oculta):
        grupo = self._grupos.get(self._grupo_de_zona.get(zona))
        if grupo:
            grupo.set_oculta(zona, oculta)
        tile = self.zona_frames.get(zona)
        if tile and not oculta:
            tile.video_label.clear()
            tile.video_label.setText("Conectando...")
            tile.estado_label.setText("Estado: conectando...")

    def _emitir_comando_manual(self):
        texto = self.campo_comando.text().strip()
        if texto:
            self.comando_manual_enviado.emit(texto)
            self.campo_comando.clear()

    def actualizar_disponibilidad_ptz(self, zonas_con_ptz):
        """El controlador llama esto cada vez que cambian las camaras
        registradas: el manual de comandos (boton de abajo) se arma de
        nuevo con esta lista, para solo mostrar mover/presets si de verdad
        hay una camara con motor PTZ agregada ahora mismo."""
        self._zonas_con_ptz = list(zonas_con_ptz)

    def _mostrar_manual(self):
        camaras = self.camaras_para_voz()
        numeros_ptz = [n for n, clave in camaras if clave in self._zonas_con_ptz]
        html = html_manual_comandos(camaras, numeros_ptz)

        dialogo = QDialog(self)
        dialogo.setWindowTitle("Manual de comandos de voz")
        dialogo.resize(520, 560)
        layout = QVBoxLayout(dialogo)
        texto = QTextEdit()
        texto.setReadOnly(True)
        texto.setHtml(html)
        layout.addWidget(texto)
        dialogo.exec()

    def registrar_evento(self, texto):
        self.texto_log.append(texto)

    def zona_widget(self, nombre_zona):
        return self.zona_frames.get(nombre_zona)

    def microfono_seleccionado(self):
        """None = microfono por defecto de Windows; si no, el indice del
        dispositivo elegido en el desplegable."""
        return self.combo_microfono.currentData()

    def set_boton_confirmar_urgente(self, urgente):
        """Pone el boton de fatiga en rojo cuando hay que confirmar: si se
        queda gris (habilitado pero sin cambiar de color) no se nota que ya
        toca hacer clic."""
        if urgente:
            self.btn_confirmar.setStyleSheet(
                "background:#c0392b; color:white; font-weight:bold; border:2px solid #ff6b5b;"
            )
        else:
            self.btn_confirmar.setStyleSheet("")

    def set_alarma_sonando(self, sonando, zonas=()):
        if sonando:
            self.btn_silenciar_alarma.setText(f"SILENCIAR ALARMA - camara tapada: {', '.join(zonas)}")
            self.btn_silenciar_alarma.setStyleSheet(
                "background:#c0392b; color:white; font-weight:bold; border:2px solid #ff6b5b; padding:8px;"
            )
        else:
            self.btn_silenciar_alarma.setText("Silenciar alarma")
            self.btn_silenciar_alarma.setStyleSheet("")
        self.btn_silenciar_alarma.setEnabled(sonando)
