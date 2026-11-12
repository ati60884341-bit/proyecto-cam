"""Bloque del Centro de Monitoreo que agrupa las camaras de UN grabador
(DVR o NVR) - o las camaras independientes (USB / IP sueltas) - bajo un
encabezado propio, para que se vea de un vistazo que camara pertenece a
que equipo. Tambien lleva el menu "Ocultas" para volver a mostrar las
camaras suspendidas de ese grabador."""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QToolButton, QVBoxLayout

ESTILO_GRUPO = (
    "QFrame#grupoGrabador { border: 1px solid #2c4a5a; border-radius: 8px; background: rgba(10, 25, 35, 160); }"
)


class GrupoGrabador(QFrame):
    mostrar_zona = pyqtSignal(str)

    def __init__(self, titulo, columnas=2, parent=None):
        super().__init__(parent)
        self.setObjectName("grupoGrabador")
        self.setStyleSheet(ESTILO_GRUPO)
        self._columnas = columnas
        self._tiles = []          # ZonaFrame en orden de llegada
        self._ocultas = []        # nombres de zona ocultas, en orden

        layout = QVBoxLayout(self)
        encabezado = QHBoxLayout()
        self.lbl_titulo = QLabel()
        self.lbl_titulo.setStyleSheet("color: #7fd6e8; font-weight: bold; font-size: 13px; border: none;")
        encabezado.addWidget(self.lbl_titulo, stretch=1)

        self.btn_ocultas = QToolButton()
        self.btn_ocultas.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_ocultas.setToolTip("Camaras suspendidas de este grupo: elija una para volver a mostrarla")
        self._menu_ocultas = QMenu(self.btn_ocultas)
        self.btn_ocultas.setMenu(self._menu_ocultas)
        encabezado.addWidget(self.btn_ocultas)
        layout.addLayout(encabezado)

        self.grid = QGridLayout()
        layout.addLayout(self.grid)
        self.lbl_vacio = QLabel("Todas las camaras de este grupo estan ocultas.")
        self.lbl_vacio.setStyleSheet("color: #888; font-style: italic; border: none;")
        layout.addWidget(self.lbl_vacio)

        self._titulo_base = titulo
        self._actualizar()

    # ---------------- titulo ----------------
    def set_titulo(self, titulo):
        self._titulo_base = titulo
        self._actualizar()

    # ---------------- tiles ----------------
    def agregar_tile(self, tile):
        self._tiles.append(tile)
        self._reacomodar()

    def quitar_tile(self, tile):
        if tile in self._tiles:
            self._tiles.remove(tile)
        if tile.nombre_zona in self._ocultas:
            self._ocultas.remove(tile.nombre_zona)
        self.grid.removeWidget(tile)
        self._reacomodar()

    def cantidad(self):
        return len(self._tiles)

    def set_oculta(self, zona, oculta):
        if oculta and zona not in self._ocultas:
            self._ocultas.append(zona)
        elif not oculta and zona in self._ocultas:
            self._ocultas.remove(zona)
        self._reacomodar()

    def _reacomodar(self):
        """Vuelve a ubicar solo las visibles, sin huecos donde estaba una oculta."""
        for tile in self._tiles:
            self.grid.removeWidget(tile)
        posicion = 0
        for tile in self._tiles:
            if tile.nombre_zona in self._ocultas:
                tile.hide()
                continue
            fila, columna = divmod(posicion, self._columnas)
            self.grid.addWidget(tile, fila, columna)
            tile.show()
            posicion += 1
        self._actualizar()

    def _actualizar(self):
        total = len(self._tiles)
        visibles = total - len(self._ocultas)
        sufijo = f"  ·  {total} camara{'s' if total != 1 else ''}"
        if self._ocultas:
            sufijo += f" ({visibles} visible{'s' if visibles != 1 else ''})"
        self.lbl_titulo.setText(self._titulo_base + sufijo)

        self._menu_ocultas.clear()
        for zona in self._ocultas:
            accion = self._menu_ocultas.addAction(f"Mostrar {zona}")
            accion.triggered.connect(lambda _=False, z=zona: self.mostrar_zona.emit(z))
        if len(self._ocultas) > 1:
            self._menu_ocultas.addSeparator()
            todas = self._menu_ocultas.addAction("Mostrar todas")
            todas.triggered.connect(lambda: [self.mostrar_zona.emit(z) for z in list(self._ocultas)])
        self.btn_ocultas.setText(f"Ocultas ({len(self._ocultas)})")
        self.btn_ocultas.setVisible(bool(self._ocultas))
        self.lbl_vacio.setVisible(total > 0 and visibles == 0)
