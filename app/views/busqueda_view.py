"""Busqueda de personas vistas por la IA: "polo rojo y pantalon azul cerca
de la puerta" -> fotos de cada avistamiento con camara, hora y zona."""
import os
import time

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QListView, QPushButton,
    QVBoxLayout, QWidget,
)

from app.services.ia_personas import NOMBRES_COLOR
from app.views.UI.tema import COLOR_TEXTO_MUTED

CUALQUIERA = "Cualquiera"


class BusquedaView(QWidget):
    buscar_pedido = Signal()
    texto_libre = Signal(str)
    mostrada = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(18, 14, 18, 14)

        titulo = QLabel("Búsqueda de personas")
        titulo.setStyleSheet("font-size: 20px; font-weight: 600; color: white;")
        raiz.addWidget(titulo)
        sub = QLabel("Todo lo que vio la IA de personas en las cámaras que la tienen activada "
                     "(casilla \"IA: detectar personas\" en Ampliar).")
        sub.setStyleSheet(f"color: {COLOR_TEXTO_MUTED};")
        sub.setWordWrap(True)
        raiz.addWidget(sub)

        fila = QHBoxLayout()
        self.txt = QLineEdit()
        self.txt.setPlaceholderText("Describa a la persona, ej.: polo rojo y pantalón azul cerca de la puerta")
        self.txt.returnPressed.connect(lambda: self.texto_libre.emit(self.txt.text()))
        fila.addWidget(self.txt, stretch=1)
        btn = QPushButton("Buscar")
        btn.clicked.connect(lambda: self.texto_libre.emit(self.txt.text()))
        fila.addWidget(btn)
        raiz.addLayout(fila)

        filtros = QHBoxLayout()
        self.cmb_arriba = self._combo_colores()
        self.cmb_abajo = self._combo_colores()
        self.txt_zona = QLineEdit()
        self.txt_zona.setPlaceholderText("zona (ej. puerta)")
        self.txt_zona.returnPressed.connect(self.buscar_pedido.emit)
        self.cmb_camara = QComboBox()
        self.cmb_camara.addItem("Todas")
        for etiqueta, control in [("Ropa de arriba:", self.cmb_arriba), ("Ropa de abajo:", self.cmb_abajo),
                                  ("Zona:", self.txt_zona), ("Cámara:", self.cmb_camara)]:
            lbl = QLabel(etiqueta)
            lbl.setStyleSheet(f"color: {COLOR_TEXTO_MUTED};")
            filtros.addWidget(lbl)
            filtros.addWidget(control)
        for c in (self.cmb_arriba, self.cmb_abajo, self.cmb_camara):
            c.activated.connect(lambda _i: self.buscar_pedido.emit())
        filtros.addStretch()
        raiz.addLayout(filtros)

        self.lbl_resultado = QLabel()
        self.lbl_resultado.setStyleSheet("color: #7fd6e8;")
        raiz.addWidget(self.lbl_resultado)

        self.lista = QListWidget()
        self.lista.setViewMode(QListView.ViewMode.IconMode)
        self.lista.setIconSize(QSize(110, 180))
        self.lista.setGridSize(QSize(190, 285))
        self.lista.setResizeMode(QListView.ResizeMode.Adjust)
        self.lista.setMovement(QListView.Movement.Static)
        self.lista.setWordWrap(True)
        self.lista.setSpacing(6)
        self.lista.itemDoubleClicked.connect(self._abrir)
        raiz.addWidget(self.lista, stretch=1)

    def _combo_colores(self):
        c = QComboBox()
        c.addItem(CUALQUIERA)
        c.addItems(NOMBRES_COLOR)
        return c

    def showEvent(self, evento):
        self.mostrada.emit()
        super().showEvent(evento)

    # ---- filtros ----
    def filtros(self):
        def valor(combo):
            return None if combo.currentText() in (CUALQUIERA, "Todas") else combo.currentText()
        return {"arriba": valor(self.cmb_arriba), "abajo": valor(self.cmb_abajo),
                "zona": self.txt_zona.text().strip() or None, "camara": valor(self.cmb_camara)}

    def poner_filtros(self, arriba, abajo, zona):
        self.cmb_arriba.setCurrentText(arriba or CUALQUIERA)
        self.cmb_abajo.setCurrentText(abajo or CUALQUIERA)
        self.txt_zona.setText(zona or "")

    def set_camaras(self, nombres):
        actual = self.cmb_camara.currentText()
        self.cmb_camara.clear()
        self.cmb_camara.addItem("Todas")
        self.cmb_camara.addItems(nombres)
        self.cmb_camara.setCurrentText(actual if actual in nombres else "Todas")

    # ---- resultados ----
    def mostrar(self, avistamientos):
        self.lista.clear()
        if not avistamientos:
            self.lbl_resultado.setText("Sin resultados. Active la IA en una cámara y camine frente a ella.")
            return
        self.lbl_resultado.setText(f"{len(avistamientos)} avistamiento(s), del más reciente al más antiguo. "
                                   "Doble clic para ver la foto.")
        for a in avistamientos:
            lugar = ""
            if a.get("zona"):
                lugar = f"\n{'en' if a.get('relacion') == 'en' else 'cerca de'} {a['zona']}"
            texto = (f"{time.strftime('%d/%m %H:%M:%S', time.localtime(a['t']))}\n{a['camara']}\n"
                     f"arriba {a.get('arriba') or '?'} · abajo {a.get('abajo') or '?'}{lugar}")
            item = QListWidgetItem(QIcon(QPixmap(a["ruta"])), texto)
            item.setData(Qt.ItemDataRole.UserRole, a["ruta"])
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.lista.addItem(item)

    def _abrir(self, item):
        ruta = item.data(Qt.ItemDataRole.UserRole)
        if ruta and os.path.exists(ruta):
            os.startfile(ruta)
