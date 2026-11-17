from app.services import avistamientos


class BusquedaController:
    def __init__(self, view, monitoreo_controller):
        self.view = view
        self.monitoreo = monitoreo_controller
        view.texto_libre.connect(self._buscar_texto)
        view.buscar_pedido.connect(self.buscar)
        view.mostrada.connect(self._al_mostrar)

    def _al_mostrar(self):
        self.view.set_camaras(sorted(c["Nombre"] for c in self.monitoreo.camaras_por_zona.values()))
        self.buscar()

    def _buscar_texto(self, texto):
        if texto.strip():
            f = avistamientos.interpretar_busqueda(texto)
            self.view.poner_filtros(f["arriba"], f["abajo"], f["zona"])
        self.buscar()

    def buscar(self):
        self.view.mostrar(avistamientos.buscar(**self.view.filtros()))
