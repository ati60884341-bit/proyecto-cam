import math

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QPushButton,
    QLabel, QLineEdit, QTextEdit, QCheckBox, QDialog, QScrollArea,
)

from app.views.UI.zona_frame import ZonaFrame

MANUAL_COMANDOS_HTML = """
<h2>Manual de comandos de voz</h2>
<p>Formato simple: diga la <b>zona</b> y luego la <b>accion</b> (en cualquier
orden). No hace falta ninguna palabra de activacion. El campo de texto manual
del panel de la derecha acepta las mismas frases, sin necesidad de microfono.</p>
<p>Zonas validas: <b>ingreso, patio, estacionamiento, pasillo</b> (o el nombre
de cualquier zona nueva que haya agregado en "Camaras").</p>

<h3>Ver una zona en pantalla completa</h3>
<ul>
<li><i>"&lt;zona&gt; ampliar"</i> — ej. "patio ampliar"</li>
<li><i>"&lt;zona&gt; mostrar"</i> / <i>"&lt;zona&gt; pantalla completa"</i></li>
</ul>

<h3>Capturar evidencia</h3>
<ul>
<li><i>"&lt;zona&gt; capturar"</i> — ej. "ingreso capturar"</li>
<li><i>"&lt;zona&gt; foto"</i> / <i>"&lt;zona&gt; evidencia"</i></li>
</ul>

<h3>Zoom digital</h3>
<ul>
<li><i>"&lt;zona&gt; acercar"</i> / <i>"&lt;zona&gt; zoom"</i> — acerca un paso</li>
<li><i>"&lt;zona&gt; alejar"</i> — aleja un paso</li>
<li><i>"&lt;zona&gt; zoom normal"</i> / <i>"&lt;zona&gt; quitar zoom"</i> — vuelve a 1x</li>
</ul>
<p>El zoom tambien se aplica a la vista ampliada de esa zona si esta abierta.</p>

<h3>Mover la camara (PTZ real, ej. Tapo C510W)</h3>
<ul>
<li><i>"&lt;zona&gt; mover izquierda"</i> — ej. "patio mover izquierda"</li>
<li><i>"&lt;zona&gt; mover derecha"</i></li>
<li><i>"&lt;zona&gt; mover arriba"</i></li>
<li><i>"&lt;zona&gt; mover abajo"</i></li>
<li><i>"&lt;zona&gt; girar izquierda"</i></li>
</ul>
<p>Solo funciona con camaras RTSP que tengan motor Pan/Tilt y soporten ONVIF
(como la Tapo C510W). Se necesita el usuario/clave de la "Cuenta de camara"
(RTSP) configurados en la app Tapo; el puerto ONVIF de Tapo es 2020.</p>

<h3>Vista general</h3>
<ul>
<li><i>"vista general"</i> (no necesita zona)</li>
</ul>

<h3>Modo panico silencioso</h3>
<p>No es un comando de voz (para no delatar al operador): active primero la
casilla "Activar deteccion de gesto" (se apaga por defecto para no competir
con el arranque de las camaras y ahorrar CPU/RAM); luego levante una mano
(o ambas) frente a la camara de <b>Ingreso</b> durante 3 segundos. Si no
quiere activar la deteccion de gesto, use el boton "Simular Modo Panico" del
panel derecho, que funciona siempre.</p>

<h3>Ejemplos completos</h3>
<ul>
<li>"patio ampliar"</li>
<li>"ingreso capturar"</li>
<li>"estacionamiento acercar"</li>
<li>"estacionamiento alejar"</li>
<li>"patio mover derecha"</li>
<li>"vista general"</li>
</ul>
"""


class DashboardView(QWidget):
    comando_manual_enviado = pyqtSignal(str)
    asistente_voz_alternado = pyqtSignal(bool)
    panico_manual = pyqtSignal()
    fatiga_confirmada = pyqtSignal()
    capturar_evidencia = pyqtSignal(str)
    ampliar_zona = pyqtSignal(str)
    reconectar_zona = pyqtSignal(str)
    deteccion_gesto_alternada = pyqtSignal(bool)

    def __init__(self, camaras, parent=None):
        super().__init__(parent)
        self.zona_frames = {}
        self._siguiente_posicion = 0
        self._columnas = 2

        layout_raiz = QHBoxLayout(self)

        # -------- panel izquierdo: zonas (QGridLayout de QFrame, dinamico) --------
        self.panel_zonas = QWidget()
        self.grid = QGridLayout(self.panel_zonas)
        for camara in camaras:
            # una tarjeta por ZONA, nunca por camara: si la lista inicial
            # trae mas de una camara activa para la misma zona (pasa si
            # "quitar camara" dejo una vieja sin desactivar), no se deben
            # crear dos tarjetas huerfanas para esa zona
            self.agregar_zona_frame(camara)

        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setWidget(self.panel_zonas)
        layout_raiz.addWidget(desplazable, stretch=3)

        # -------- panel derecho: asistente de voz, panico, fatiga --------
        panel_derecho = QVBoxLayout()

        grupo_voz = QGroupBox("Asistente de comandos de voz")
        v = QVBoxLayout(grupo_voz)
        self.chk_voz = QCheckBox("Activar microfono (manos libres)")
        self.chk_voz.toggled.connect(self.asistente_voz_alternado.emit)
        v.addWidget(self.chk_voz)
        self.lbl_estado_voz = QLabel("Asistente apagado")
        v.addWidget(self.lbl_estado_voz)

        fila_manual = QHBoxLayout()
        self.campo_comando = QLineEdit()
        self.campo_comando.setPlaceholderText('Ej: "patio ampliar"')
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

        grupo_panico = QGroupBox("Modo panico silencioso")
        p = QVBoxLayout(grupo_panico)
        p.addWidget(QLabel("Gesto: una o ambas manos arriba, 3 segundos, frente a la camara de Ingreso."))
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
        r.addWidget(self.texto_log)
        panel_derecho.addWidget(grupo_registro, stretch=1)

        layout_raiz.addLayout(panel_derecho, stretch=2)

    # ---------------- zonas / camaras ----------------
    def _agregar_tile(self, camara):
        zf = ZonaFrame(camara["Zona"], camara["Nombre"])
        zf.capturar_evidencia.connect(self.capturar_evidencia.emit)
        zf.ampliar_zona.connect(self.ampliar_zona.emit)
        zf.reconectar_zona.connect(self.reconectar_zona.emit)
        fila, columna = divmod(self._siguiente_posicion, self._columnas)
        self.grid.addWidget(zf, fila, columna)
        self._siguiente_posicion += 1
        self.zona_frames[camara["Zona"]] = zf
        return zf

    def agregar_zona_frame(self, camara):
        """Usado por el controlador al agregar una camara nueva (cualquier
        marca). Si la zona ya tenia un tile, se reutiliza (se reemplaza la
        camara que alimenta ese recuadro, incluso si estaba quitada); si es
        una zona nueva, se agrega un recuadro nuevo a la grilla."""
        existente = self.zona_frames.get(camara["Zona"])
        if existente:
            existente.titulo.setText(f"{camara['Zona']}  —  {camara['Nombre']}")
            existente.video_label.setText("Conectando...")
            existente._set_botones_habilitados(True)
            return existente
        return self._agregar_tile(camara)

    def marcar_zona_removida(self, zona):
        tile = self.zona_frames.get(zona)
        if tile:
            tile.actualizar_estado("removida")

    def _emitir_comando_manual(self):
        texto = self.campo_comando.text().strip()
        if texto:
            self.comando_manual_enviado.emit(texto)
            self.campo_comando.clear()

    def _mostrar_manual(self):
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Manual de comandos de voz")
        dialogo.resize(560, 600)
        layout = QVBoxLayout(dialogo)
        texto = QTextEdit()
        texto.setReadOnly(True)
        texto.setHtml(MANUAL_COMANDOS_HTML)
        layout.addWidget(texto)
        dialogo.exec()

    def registrar_evento(self, texto):
        self.texto_log.append(texto)

    def zona_widget(self, nombre_zona):
        return self.zona_frames.get(nombre_zona)

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
