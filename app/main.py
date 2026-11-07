import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMessageBox

from app.views.login_view import LoginView
from app.views.UI.splash_view import SplashView
from app.views.UI.tema import HOJA_ESTILOS_GLOBAL, aplicar_paleta_oscura
from app.views.UI.animacion_botones import AnimadorHoverBotones
from app.controllers.auth_controller import AuthController


def _instalar_manejador_errores(app):
    """Sin esto, una excepcion dentro de un slot de Qt (ej. al iniciar
    sesion) puede cerrar la app en silencio, sin imprimir nada: aqui se
    registra el traceback completo y se avisa al usuario en vez de morir
    sin explicacion."""

    def manejador(tipo, valor, tb):
        texto = "".join(traceback.format_exception(tipo, valor, tb))
        print(texto, file=sys.stderr, flush=True)
        try:
            QMessageBox.critical(
                None, "Error inesperado",
                f"Ocurrio un error y la operacion no se pudo completar:\n\n{valor}\n\n"
                "Vea run_app.log para el detalle tecnico.",
            )
        except Exception:
            pass

    sys.excepthook = manejador


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # paleta oscura DE VERDAD (QPalette, no solo QSS) + hoja de estilos:
    # entre las dos cubren tanto los controles especificos (botones, campos,
    # tablas) como los widgets "en blanco" (QWidget simple, QStackedWidget)
    # que una hoja de estilos sola no pinta - sin esto se veian grises/claros
    # de fondo, sin relacion con la paleta navy/teal del resto del programa.
    # Tambien evita que la app dependa de si Windows esta en modo claro u
    # oscuro en cada laptop del equipo - ver app/views/UI/tema.py
    aplicar_paleta_oscura(app)
    app.setStyleSheet(HOJA_ESTILOS_GLOBAL)
    # atenuado suave al pasar el mouse sobre cualquier boton del programa,
    # sin tener que tocar cada pestana por separado - ver animacion_botones.py
    animador_hover = AnimadorHoverBotones(app)
    app.installEventFilter(animador_hover)
    _instalar_manejador_errores(app)

    login_view = LoginView()
    auth_controller = AuthController(login_view)

    def al_salir():
        if auth_controller.app_controller:
            auth_controller.app_controller.detener()

    app.aboutToQuit.connect(al_salir)

    # splash animada unos segundos antes del login, para que la identidad
    # visual del programa (la escena nocturna) se sienta desde que se abre,
    # no recien despues de iniciar sesion
    splash = SplashView()
    splash.terminado.connect(lambda: (splash.close(), login_view.show()))
    splash.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
