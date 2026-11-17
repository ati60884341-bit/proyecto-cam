import time

from PySide6.QtCore import QSettings

from app.services.mapa_service import RecorridoMapa
from app.services.ia_personas import COLORES_RGB


class MapaController:
    """Une el movimiento de cada camara (MonitoreoController) con la pestana
    Mapa del lugar. Plano y posiciones se guardan en ESTA PC (QSettings),
    igual que las camaras ocultas y la linea virtual."""

    def __init__(self, view, monitoreo_controller):
        self.view = view
        self.monitoreo = monitoreo_controller
        self.recorrido = RecorridoMapa()
        self._ajustes = QSettings("ProyectoCAM", "CentroMonitoreo")

        view.set_plano(self._ajustes.value("mapa/plano", ""))
        view.plano_elegido.connect(self._guardar_plano)
        view.reiniciar_pedido.connect(self._reiniciar)
        view.mostrada.connect(self.refrescar_camaras)
        view.lienzo.posicion_cambiada.connect(self._guardar_posicion)
        monitoreo_controller.oyentes_movimiento.append(self._on_movimiento)
        monitoreo_controller.oyentes_personas.append(self._on_personas)
        self.refrescar_camaras()

    def _on_personas(self, clave, personas):
        """Personas de una camara CALIBRADA: puntos en vivo sobre el plano,
        pintados con el color de su ropa (arriba / abajo)."""
        puntos = [(p["plano"], COLORES_RGB.get(p.get("arriba"), (200, 200, 200)),
                   COLORES_RGB.get(p.get("abajo"), (90, 90, 90))) for p in personas if p.get("plano")]
        self.view.lienzo.personas_vivas[clave] = (time.time(), puntos)

    def _nombre(self, clave):
        return self.monitoreo.camaras_por_zona.get(clave, {}).get("Nombre", clave)

    def refrescar_camaras(self):
        """Lista vigente (se agregan/quitan/ocultan camaras en caliente)."""
        camaras = {}
        for clave, cam in self.monitoreo.camaras_por_zona.items():
            if clave in self.monitoreo._zonas_ocultas:
                continue
            valor = self._ajustes.value(f"mapa/pos/{cam['IdCamara']}", "")
            try:
                x, y = (float(v) for v in str(valor).split(","))
                pos = (x, y)
            except ValueError:
                pos = None
            camaras[clave] = {"nombre": cam["Nombre"], "pos": pos}
        self.view.lienzo.set_camaras(camaras)

    def _guardar_posicion(self, clave, x, y):
        cam = self.monitoreo.camaras_por_zona.get(clave)
        if cam:
            self._ajustes.setValue(f"mapa/pos/{cam['IdCamara']}", f"{x:.4f},{y:.4f}")

    def _guardar_plano(self, ruta):
        self._ajustes.setValue("mapa/plano", ruta)
        self.view.set_plano(ruta)

    def _reiniciar(self):
        self.recorrido.reiniciar()
        lienzo = self.view.lienzo
        lienzo.activas, lienzo.calor, lienzo.flujos = set(), {}, {}
        self.view.limpiar()
        lienzo.update()

    def _on_movimiento(self, clave, nivel):
        paso = self.recorrido.actualizar(clave, nivel, time.time())
        lienzo = self.view.lienzo
        lienzo.activas = self.recorrido.activas()
        lienzo.calor = self.recorrido.calor
        lienzo.flujos = self.recorrido.flujos
        if not paso:
            return
        origen, destino = paso
        lienzo.animar_paso(origen, destino)
        self.view.agregar_paso(f"{time.strftime('%H:%M:%S')}   {self._nombre(origen)} → {self._nombre(destino)}")
        mas_usado = max(self.recorrido.flujos.items(), key=lambda kv: kv[1])
        (a, b), n = mas_usado
        self.view.set_resumen(
            f"{len(self.recorrido.pasos)} pasos detectados. Camino mas usado: "
            f"{self._nombre(a)} → {self._nombre(b)} ({n} veces)."
        )
