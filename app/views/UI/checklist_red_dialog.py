import os
import webbrowser

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
)

from app.config import MANUALES_DIR

_ITEMS = [
    "Hay un cable de red (UTP) entre el puerto LAN del DVR/NVR y un switch o router —\n"
    "sin esto, ni el ping ni el programa lo van a encontrar, aunque tenga video.",
    "Esta laptop esta en esa MISMA red (por WiFi o cable) — compruebalo en el panel\n"
    "\"Mi red\" de abajo antes de seguir.",
    "Si llevas internet portatil (celular/modem), va por OTRO adaptador, sin conectarlo\n"
    "al switch/router del DVR.",
]


class ChecklistRedDialog(QDialog):
    """Se muestra UNA vez por sesion, la primera vez que se entra a "NVR /
    DVR": tres casillas que hay que marcar antes de poder continuar. No
    reemplaza el manual ilustrado (tiene un boton para abrirlo), pero
    evita que alguien pierda tiempo armando una conexion que la red ni
    siquiera deja llegar, por no haber revisado lo basico primero."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Antes de registrar un grabador - checklist de red")
        self.setModal(True)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Confirma esto ANTES de registrar el grabador - es la causa mas comun de\n"
            "\"el programa no lo encuentra\" en terreno:"
        ))

        self._casillas = []
        for texto in _ITEMS:
            casilla = QCheckBox(texto)
            casilla.stateChanged.connect(self._actualizar_boton)
            layout.addWidget(casilla)
            self._casillas.append(casilla)

        fila_botones = QHBoxLayout()
        btn_manual = QPushButton("Ver manual ilustrado")
        btn_manual.clicked.connect(self._abrir_manual)
        fila_botones.addWidget(btn_manual)
        fila_botones.addStretch()

        self.btn_continuar = QPushButton("Ya revise esto, continuar")
        self.btn_continuar.setEnabled(False)
        self.btn_continuar.clicked.connect(self.accept)
        fila_botones.addWidget(self.btn_continuar)
        layout.addLayout(fila_botones)

    def _actualizar_boton(self, _estado=None):
        self.btn_continuar.setEnabled(all(c.isChecked() for c in self._casillas))

    def _abrir_manual(self):
        ruta = os.path.join(MANUALES_DIR, "conectar_red_dvr.html")
        webbrowser.open(f"file:///{ruta}")
