import traceback

from PyQt6.QtWidgets import QMessageBox

from app.models import camara_model, zona_model


class CamaraController:
    """Alta/baja de camaras de cualquier marca (adaptador universal RTSP/USB),
    segun el pilar 2 de la propuesta del proyecto."""

    def __init__(self, view, usuario, on_camara_agregada, on_camara_quitada):
        self.view = view
        self.usuario = usuario
        self.on_camara_agregada = on_camara_agregada
        self.on_camara_quitada = on_camara_quitada
        self._camaras = []

        self.view.agregar_solicitado.connect(self.agregar)
        self.view.quitar_solicitado.connect(self.quitar)
        self.view.refrescar_solicitado.connect(self.cargar)
        self.view.permitir_quitar(usuario["Rol"] == "Administrador")
        self.cargar()

    def cargar(self):
        self.view.set_zonas_disponibles([z["Nombre"] for z in zona_model.listar()])
        self._camaras = camara_model.listar()
        self.view.cargar(self._camaras)

    def agregar(self, datos):
        try:
            zona = zona_model.obtener_o_crear(datos["zona"])
            id_camara = camara_model.crear(
                zona["IdZona"], datos["nombre"], datos["marca"], datos["tipo_conexion"], datos["url"],
            )
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(self.view, "No se pudo agregar la camara", str(exc))
            return
        camara_completa = {
            "IdCamara": id_camara, "IdZona": zona["IdZona"], "Zona": zona["Nombre"],
            "Nombre": datos["nombre"], "Marca": datos["marca"],
            "TipoConexion": datos["tipo_conexion"], "UrlConexion": datos["url"], "Estado": "Activa",
        }
        self.cargar()
        # la confirmacion se ve en la bitacora del Centro de Monitoreo (sin
        # dialogo modal, para no interrumpir el flujo de la demo)
        self.on_camara_agregada(camara_completa)

    def quitar(self, id_camara):
        if self.usuario["Rol"] != "Administrador":
            QMessageBox.warning(self.view, "Permiso denegado", "Solo un administrador puede quitar camaras.")
            return
        camara = next((c for c in self._camaras if c["IdCamara"] == id_camara), None)
        if not camara:
            return
        confirmacion = QMessageBox.question(
            self.view, "Confirmar", f"¿Quitar la camara \"{camara['Nombre']}\" de la zona \"{camara['Zona']}\"?"
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return
        try:
            camara_model.actualizar_estado(id_camara, "Inactiva")
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(self.view, "No se pudo quitar la camara", str(exc))
            return
        self.cargar()
        self.on_camara_quitada(camara["Zona"])
