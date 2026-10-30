from app.models import turno_model


class TurnoController:
    def __init__(self, view, usuario):
        self.view = view
        self.usuario = usuario
        self.id_turno_actual = None

        self.view.abrir_turno_solicitado.connect(self.abrir)
        self.view.cerrar_turno_solicitado.connect(self.cerrar)
        self.view.refrescar_solicitado.connect(self.cargar_historial)

        abierto = turno_model.turno_abierto(usuario["IdUsuario"])
        if abierto:
            self.id_turno_actual = abierto["IdTurno"]
        self.view.set_turno_abierto(abierto is not None)
        self.cargar_historial()

    def abrir(self):
        self.id_turno_actual = turno_model.abrir(self.usuario["IdUsuario"])
        self.view.set_turno_abierto(True)

    def cerrar(self):
        if self.id_turno_actual:
            turno_model.cerrar(self.id_turno_actual)
            self.id_turno_actual = None
        self.view.set_turno_abierto(False)
        self.cargar_historial()

    def cargar_historial(self):
        self.view.cargar_historial(turno_model.listar_historial())
