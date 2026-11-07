import traceback

from PyQt6.QtWidgets import QMessageBox

from app.models import usuario_model
from app.controllers.app_controller import AppController
from app.services.actualizador import HiloBuscarActualizacion
from app.views.UI.dialogo_actualizacion import DialogoActualizacion


class AuthController:
    def __init__(self, login_view):
        self.login_view = login_view
        self.login_view.intento_login.connect(self.manejar_login)
        self.app_controller = None
        self._hilo_buscar_actualizacion = None

    def manejar_login(self, nombre_usuario, clave):
        if not nombre_usuario or not clave:
            self.login_view.mostrar_error("Ingrese usuario y clave.")
            return
        try:
            usuario = usuario_model.autenticar(nombre_usuario, clave)
        except Exception as exc:
            traceback.print_exc()
            self.login_view.mostrar_error(f"No se pudo conectar a la base de datos:\n{exc}")
            return
        if not usuario:
            self.login_view.mostrar_error("Usuario o clave incorrectos.")
            return
        self._iniciar_sesion(usuario)

    def _iniciar_sesion(self, usuario):
        # si algo falla construyendo el Centro de Monitoreo, no se pierde la
        # ventana de login: se avisa el error y se puede reintentar
        try:
            app_controller = AppController(usuario)
        except Exception as exc:
            traceback.print_exc()
            self.login_view.mostrar_error(f"No se pudo abrir el Centro de Monitoreo:\n{exc}")
            return

        self.app_controller = app_controller
        self.app_controller.main_window.btn_salir.clicked.connect(self._cerrar_sesion)
        self.app_controller.show()
        self.login_view.close()
        self._buscar_actualizacion()

    def _buscar_actualizacion(self):
        """Consulta GitHub Releases en segundo plano (no atrasa el login) y,
        si hay una version mas nueva publicada, ofrece actualizar - ver
        app/services/actualizador.py. Sin internet o sin ninguna release
        todavia, simplemente no pasa nada (no es un error para el usuario)."""
        self._hilo_buscar_actualizacion = HiloBuscarActualizacion()
        self._hilo_buscar_actualizacion.encontrada.connect(self._ofrecer_actualizacion)
        self._hilo_buscar_actualizacion.start()

    def _ofrecer_actualizacion(self, info):
        if self.app_controller is None:
            return  # la sesion ya se cerro mientras se consultaba
        DialogoActualizacion(info, self.app_controller.main_window).exec()

    def _cerrar_sesion(self):
        if self.app_controller:
            self.app_controller.detener()
            self.app_controller.main_window.close()
            self.app_controller = None
        self.login_view.campo_usuario.clear()
        self.login_view.campo_clave.clear()
        self.login_view.show()
