"""Hoja de estilos global del programa: un solo lugar para que TODOS los
controles (botones, campos, tablas, combos...) de TODAS las pestanas usen
la paleta navy/teal de la escena nocturna, en vez del gris por defecto de
Qt/Windows. Se aplica una sola vez, en app.setStyleSheet() (ver app/main.py),
así no hay que tocar cada vista una por una - y cualquier boton que ya tenga
su propio setStyleSheet (ej. los rojos de "Quitar"/"Cerrar sesion"/"Panico")
lo sigue ganando, porque el estilo puesto directo en un widget tiene mas
prioridad que esta hoja general.

No se le pone fondo a QFrame/QWidget en general a proposito: FondoNocturno
(ver fondo_nocturno.py) es un QFrame que pinta su propio fondo a mano
(paintEvent), y una regla ancha tipo "QFrame { background: ... }" aca
competiria con eso. Por eso el tema solo toca clases de control "planas"
(botones, campos, tablas...), nunca QFrame/QWidget en general.

El fondo gris que se veia en la pestana NVR/DVR y otras NO era un problema
de la hoja de estilos: es la paleta CLARA por defecto de Fusion asomando
en los widgets "en blanco" (QWidget simple, QStackedWidget, QScrollArea)
que una hoja de estilos no cubre sola. aplicar_paleta_oscura() pone una
paleta de Qt oscura de verdad para esos casos, para que la app se vea
igual en las 4 laptops del equipo sin importar si Windows esta en modo
claro u oscuro en cada una."""

import os
import tempfile

from PyQt6.QtGui import QColor, QPalette

from app.views.UI.iconos import pixmap_icono

# mismos colores que el resto del tema, para que cualquier vista con graficos
# propios (matplotlib, etc. - ver reportes_view.py) no invente los suyos
COLOR_FONDO = "#12151d"
COLOR_PANEL = "#171b24"
COLOR_BORDE = "#2a303c"
COLOR_TEXTO = "#e7e9ee"
COLOR_TEXTO_MUTED = "#9aa6b3"
COLOR_ACENTO = "#36d6c9"
COLOR_ACENTO_SECUNDARIO = "#e0935a"


def aplicar_paleta_oscura(app):
    paleta = QPalette()
    paleta.setColor(QPalette.ColorRole.Window, QColor("#12151d"))
    paleta.setColor(QPalette.ColorRole.WindowText, QColor("#e7e9ee"))
    paleta.setColor(QPalette.ColorRole.Base, QColor("#171b24"))
    paleta.setColor(QPalette.ColorRole.AlternateBase, QColor("#1c2128"))
    paleta.setColor(QPalette.ColorRole.ToolTipBase, QColor("#171b24"))
    paleta.setColor(QPalette.ColorRole.ToolTipText, QColor("#e7e9ee"))
    paleta.setColor(QPalette.ColorRole.Text, QColor("#e7e9ee"))
    paleta.setColor(QPalette.ColorRole.Button, QColor("#1c2128"))
    paleta.setColor(QPalette.ColorRole.ButtonText, QColor("#e7e9ee"))
    paleta.setColor(QPalette.ColorRole.BrightText, QColor("#ff6b6b"))
    paleta.setColor(QPalette.ColorRole.Link, QColor("#36d6c9"))
    paleta.setColor(QPalette.ColorRole.Highlight, QColor("#36d6c9"))
    paleta.setColor(QPalette.ColorRole.HighlightedText, QColor("#06201d"))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#6b7280"))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#6b7280"))
    paleta.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#6b7280"))
    app.setPalette(paleta)


HOJA_ESTILOS_GLOBAL = """
QMainWindow, QDialog { background: #12151d; }
QWidget { color: #e7e9ee; }

QPushButton {
    background: rgba(255, 255, 255, 18);
    color: #e7e9ee;
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 8px;
    padding: 8px 14px;
}
QPushButton:hover { background: rgba(54, 214, 201, 40); border-color: rgba(54, 214, 201, 140); }
QPushButton:pressed { background: rgba(54, 214, 201, 70); }
QPushButton:disabled { background: rgba(255, 255, 255, 8); color: rgba(231, 233, 238, 90); border-color: rgba(255, 255, 255, 18); }
QPushButton:checked { background: rgba(54, 214, 201, 45); border-color: #36d6c9; }

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #171b24; color: #e7e9ee; border: 1px solid #2a303c; border-radius: 7px; padding: 5px 8px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #36d6c9; }
QComboBox::drop-down { border: none; border-left: 1px solid #2a303c; width: 26px; }
QComboBox::down-arrow { image: url(__FLECHA__); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: #171b24; color: #e7e9ee; border: 1px solid #2a303c;
    selection-background-color: rgba(54, 214, 201, 45); selection-color: #ffffff;
}

QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #2a303c; border-radius: 4px; background: #171b24; }
QCheckBox::indicator:checked { background: #36d6c9; border-color: #36d6c9; }

QGroupBox {
    border: 1px solid #2a303c; border-radius: 10px; margin-top: 14px; padding-top: 10px; font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #9aa6b3; }

QTableWidget, QTableView {
    background: #12151d; alternate-background-color: #171b24; gridline-color: #262c36;
    color: #e7e9ee; border: 1px solid #2a303c; border-radius: 8px;
    selection-background-color: rgba(54, 214, 201, 45); selection-color: #ffffff;
}
QHeaderView::section {
    background: #171b24; color: #9aa6b3; padding: 6px; border: none; border-bottom: 1px solid #2a303c;
}

QProgressBar { background: rgba(255, 255, 255, 20); border: none; border-radius: 4px; text-align: center; color: #e7e9ee; }
QProgressBar::chunk { background: #36d6c9; border-radius: 4px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255, 255, 255, 40); border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: rgba(54, 214, 201, 110); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: rgba(255, 255, 255, 40); border-radius: 5px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: rgba(54, 214, 201, 110); }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""


def hoja_estilos_global():
    """La hoja de arriba con la flechita de los desplegables: al darle
    estilo a QComboBox, Qt deja de dibujar su flecha y no se notaba que era
    una lista. La flecha se dibuja al vuelo (iconos.py) y se guarda como
    PNG temporal, porque una hoja de estilos solo acepta imagenes por ruta.
    Necesita la QApplication ya creada."""
    ruta = os.path.join(tempfile.gettempdir(), "proyectocam_flecha_abajo.png")
    pixmap_icono("flecha_abajo", COLOR_TEXTO_MUTED, 24).save(ruta, "PNG")
    return HOJA_ESTILOS_GLOBAL.replace("__FLECHA__", ruta.replace("\\", "/"))
