from app.models import incidencia_model


class ReporteController:
    def __init__(self, view):
        self.view = view
        self.view.refrescar_solicitado.connect(self.cargar)
        self.cargar()

    def cargar(self):
        self.view.actualizar_graficos(incidencia_model.conteo_por_tipo(), incidencia_model.conteo_por_zona())
