from PyQt6.QtWidgets import QApplication

# tamano minimo por debajo del cual la ventana deja de ser usable (los
# controles empiezan a superponerse/cortarse)
ANCHO_MINIMO = 800
ALTO_MINIMO = 480

# deja lugar a la barra de tareas de Windows y al borde de la ventana: sin
# este margen, pedir el 100% del area disponible puede dejar la ventana
# tapando la barra de tareas o con la barra de titulo fuera de la pantalla
MARGEN_PX = 40


def tamano_adaptado(ancho_deseado, alto_deseado, margen=MARGEN_PX):
    """Tamano de ventana que entra en la pantalla actual: en un monitor
    grande devuelve (ancho_deseado, alto_deseado) sin cambios; en una laptop
    con pantalla chica (ej. 1366x768, muy comun) lo reduce para que la
    ventana no quede mas grande que el area disponible, sin bajar nunca de
    un minimo usable."""
    pantalla = QApplication.primaryScreen()
    if pantalla is None:
        return ancho_deseado, alto_deseado

    disponible = pantalla.availableGeometry()
    ancho = min(ancho_deseado, max(ANCHO_MINIMO, disponible.width() - margen))
    alto = min(alto_deseado, max(ALTO_MINIMO, disponible.height() - margen))
    return ancho, alto
