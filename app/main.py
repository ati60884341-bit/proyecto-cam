import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMessageBox

from app.views.login_view import LoginView
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
    _instalar_manejador_errores(app)

    login_view = LoginView()
    auth_controller = AuthController(login_view)

    def al_salir():
        if auth_controller.app_controller:
            auth_controller.app_controller.detener()

    app.aboutToQuit.connect(al_salir)
    login_view.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
