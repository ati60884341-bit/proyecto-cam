from app.models import incidencia_model


class IncidenciaController:
    def __init__(self, view):
        self.view = view
        self.view.refrescar_solicitado.connect(self.cargar)
        self.view.atender_solicitado.connect(self.atender)
        self.cargar()

    def cargar(self):
        self.view.cargar(incidencia_model.listar())

    def atender(self, id_incidencia):
        incidencia_model.atender(id_incidencia)
        self.cargar()
