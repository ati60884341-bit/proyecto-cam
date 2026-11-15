"""Correr con:  python tests/test_inicio_sin_sidebar.py   (sin base de datos ni camaras)

Verifica que la barra lateral queda oculta en Inicio y aparece al entrar a
cualquier otra seccion, y que vuelve a ocultarse al volver a Inicio."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from app.views.main_window import MainWindow

aplicacion = QApplication.instance() or QApplication(sys.argv)

usuario = {"NombreCompleto": "Prueba", "Rol": "Vigilante"}
ventana = MainWindow(usuario, camaras=[])
ventana.show()  # isVisible() refleja la pantalla real recien con la ventana mostrada

assert ventana._seccion_actual == "inicio", ventana._seccion_actual
assert not ventana.barra_lateral.isVisible(), "la barra lateral deberia arrancar oculta en Inicio"

ventana.mostrar_seccion("dashboard")
assert ventana.barra_lateral.isVisible(), "la barra lateral deberia verse fuera de Inicio"

ventana.mostrar_seccion("incidencias")
assert ventana.barra_lateral.isVisible(), "la barra lateral deberia seguir visible en otra seccion"

ventana.mostrar_seccion("inicio")
assert not ventana.barra_lateral.isVisible(), "la barra lateral deberia ocultarse de nuevo al volver a Inicio"

ventana.close()
print("OK: la barra lateral se oculta solo en Inicio")
