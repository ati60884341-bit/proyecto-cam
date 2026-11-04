import traceback

from PyQt6.QtWidgets import QMessageBox

from app.models import camara_model, zona_model
from app.services.camera_service import PruebaConexionThread, DeteccionCamarasUSBThread


class CamaraController:
    """Alta/baja de camaras de cualquier marca (adaptador universal RTSP/USB),
    segun el pilar 2 de la propuesta del proyecto."""

    def __init__(self, view, usuario, on_camara_agregada, on_camara_quitada, programar_arranque_nativo):
        self.view = view
        self.usuario = usuario
        self.on_camara_agregada = on_camara_agregada
        self.on_camara_quitada = on_camara_quitada
        # misma cola de arranque nativo que usa MonitoreoController: sin
        # esto, probar una conexion o detectar camaras USB desde esta
        # pestana podria abrir FFmpeg/OpenCV al mismo tiempo que una camara
        # del Centro de Monitoreo esta (re)conectando, lo que en la
        # practica resulto inestable (ver monitoreo_controller.py)
        self._programar_arranque_nativo = programar_arranque_nativo
        self._camaras = []
        self._hilo_prueba = None
        self._hilo_deteccion_usb = None

        self.view.agregar_solicitado.connect(self.agregar)
        self.view.quitar_solicitado.connect(self.quitar)
        self.view.refrescar_solicitado.connect(self.cargar)
        self.view.probar_solicitado.connect(self.probar_conexion)
        self.view.detectar_usb_solicitado.connect(self.detectar_camaras_usb)
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
                tiene_ptz=datos.get("tiene_ptz", False),
            )
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(self.view, "No se pudo agregar la camara", str(exc))
            return
        camara_completa = {
            "IdCamara": id_camara, "IdZona": zona["IdZona"], "Zona": zona["Nombre"],
            "Nombre": datos["nombre"], "Marca": datos["marca"],
            "TipoConexion": datos["tipo_conexion"], "UrlConexion": datos["url"], "Estado": "Activa",
            "TienePTZ": datos.get("tiene_ptz", False),
        }
        self.cargar()
        # la confirmacion se ve en la bitacora del Centro de Monitoreo (sin
        # dialogo modal, para no interrumpir el flujo de la demo)
        self.on_camara_agregada(camara_completa)

    def probar_conexion(self, datos):
        """Prueba la camara/canal del DVR antes de agregarla de verdad, para
        poder corregir IP/usuario/clave/canal en el sitio sin ensuciar la
        lista de camaras con intentos fallidos."""
        self.view.set_probando(True)
        self._programar_arranque_nativo(lambda: self._iniciar_prueba_conexion(datos))

    def _iniciar_prueba_conexion(self, datos):
        self._hilo_prueba = PruebaConexionThread(datos["tipo_conexion"], datos["url"])
        self._hilo_prueba.resultado.connect(self._mostrar_resultado_prueba)
        self._hilo_prueba.start()

    def _mostrar_resultado_prueba(self, ok, mensaje):
        self.view.set_probando(False)
        if ok:
            QMessageBox.information(self.view, "Prueba de conexion", mensaje)
        else:
            QMessageBox.warning(self.view, "Prueba de conexion", mensaje)

    def detectar_camaras_usb(self):
        """Prueba los indices 0..4 de camara USB/integrada: el que ocupa la
        webcam depende de cada laptop, asi que en vez de que el instalador
        adivine, se listan las que de verdad respondieron con imagen."""
        self.view.set_detectando_usb(True)
        self._programar_arranque_nativo(self._iniciar_deteccion_usb)

    def _iniciar_deteccion_usb(self):
        self._hilo_deteccion_usb = DeteccionCamarasUSBThread()
        self._hilo_deteccion_usb.resultado.connect(self._mostrar_camaras_usb)
        self._hilo_deteccion_usb.start()

    def _mostrar_camaras_usb(self, encontradas):
        self.view.set_detectando_usb(False)
        self.view.mostrar_camaras_usb_detectadas(encontradas)

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
