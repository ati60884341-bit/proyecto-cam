import traceback

from PyQt6.QtWidgets import QMessageBox

from app.models import camara_model, zona_model, dispositivo_dvr_model
from app.services.camera_service import DeteccionCanalesDVRThread


class DvrController:
    """Alta masiva de camaras a partir de UN grabador DVR/NVR (Hikvision o
    Dahua): registra el dispositivo una sola vez y da de alta una camara
    por cada canal que responda, reusando el mismo flujo de "agregar
    camara en caliente" que ya usa la pestana Camaras."""

    def __init__(self, view, usuario, on_camara_agregada, on_camara_quitada, programar_arranque_nativo):
        self.view = view
        self.usuario = usuario
        self.on_camara_agregada = on_camara_agregada
        self.on_camara_quitada = on_camara_quitada
        # misma cola de arranque nativo que usa MonitoreoController (y
        # CamaraController): sin esto, detectar varios canales de un DVR
        # abriria FFmpeg al mismo tiempo que otra camara esta (re)conectando
        self._programar_arranque_nativo = programar_arranque_nativo
        self._dispositivos = []
        self._hilo_deteccion = None

        self.view.registrar_solicitado.connect(self.registrar)
        self.view.detectar_nuevos_solicitado.connect(self.detectar_nuevos)
        self.view.quitar_solicitado.connect(self.quitar)
        self.view.refrescar_solicitado.connect(self.cargar)
        self.view.permitir_quitar(usuario["Rol"] == "Administrador")
        self.cargar()

    def cargar(self):
        self._dispositivos = dispositivo_dvr_model.listar()
        self.view.cargar(self._dispositivos)

    def _buscar(self, id_dispositivo):
        return next((d for d in self._dispositivos if d["IdDispositivo"] == id_dispositivo), None)

    # ---------------- registrar + detectar todos los canales ----------------
    def registrar(self, datos):
        try:
            id_dispositivo = dispositivo_dvr_model.crear(
                datos["nombre"], datos["marca"], datos["ip"], int(datos["puerto"]),
                datos["usuario"], datos["clave"], datos["cantidad_canales"],
                canales_ptz=datos.get("tiene_ptz", False),
            )
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(self.view, "No se pudo registrar el grabador", str(exc))
            return

        self.cargar()
        self.view.registrar_evento(
            f"[{datos['nombre']}] Grabador registrado. Probando sus {datos['cantidad_canales']} canales..."
        )
        self._iniciar_deteccion(id_dispositivo, datos, canales_a_omitir=set())

    def detectar_nuevos(self, id_dispositivo):
        """Vuelve a probar los canales de un grabador ya registrado, pero
        salta los que ya tienen una camara activa (ej. se amplio de 4 a 8
        canales, o un canal que antes no respondia ya esta conectado)."""
        dispositivo = dispositivo_dvr_model.obtener(id_dispositivo)
        if not dispositivo:
            return
        canales_existentes = dispositivo_dvr_model.canales_registrados(id_dispositivo)
        self.view.registrar_evento(f"[{dispositivo['Nombre']}] Buscando canales nuevos...")
        self._iniciar_deteccion(id_dispositivo, dispositivo, canales_a_omitir=canales_existentes)

    def _iniciar_deteccion(self, id_dispositivo, datos, canales_a_omitir):
        self.view.set_detectando(True, total=datos["cantidad_canales"])
        self._programar_arranque_nativo(
            lambda: self._ejecutar_deteccion(id_dispositivo, datos, canales_a_omitir)
        )

    def _ejecutar_deteccion(self, id_dispositivo, datos, canales_a_omitir):
        self._hilo_deteccion = DeteccionCanalesDVRThread(
            datos["marca"], datos["ip"], int(datos["puerto"]), datos["usuario"], datos["clave"],
            datos["cantidad_canales"], canales_a_omitir=canales_a_omitir,
        )
        self._hilo_deteccion.progreso.connect(self.view.actualizar_progreso)
        self._hilo_deteccion.resultado.connect(
            lambda encontrados: self._procesar_canales_detectados(id_dispositivo, datos["nombre"], encontrados)
        )
        self._hilo_deteccion.start()

    def _procesar_canales_detectados(self, id_dispositivo, nombre_dispositivo, encontrados):
        self.view.set_detectando(False)
        if not encontrados:
            self.view.registrar_evento(
                f"[{nombre_dispositivo}] No respondio ningun canal nuevo. Revise IP/usuario/clave, "
                "y que esta PC este en la misma red que el grabador."
            )
            return

        dispositivo = dispositivo_dvr_model.obtener(id_dispositivo)
        marca = dispositivo["Marca"] if dispositivo else "Hikvision"
        tiene_ptz = bool(dispositivo["CanalesPTZ"]) if dispositivo else False

        for canal_info in encontrados:
            canal = canal_info["canal"]
            zona_nombre = f"{nombre_dispositivo} Canal {canal}"
            try:
                zona = zona_model.obtener_o_crear(zona_nombre)
                id_camara = camara_model.crear(
                    zona["IdZona"], f"{nombre_dispositivo}-Canal{canal}", marca, "RTSP",
                    canal_info["url"], id_dispositivo=id_dispositivo, canal=canal, tiene_ptz=tiene_ptz,
                )
            except Exception as exc:
                traceback.print_exc()
                self.view.registrar_evento(f"[{nombre_dispositivo}] Canal {canal}: no se pudo agregar ({exc}).")
                continue

            self.view.registrar_evento(
                f"[{nombre_dispositivo}] Canal {canal}: conectado ({canal_info['resolucion']}), "
                f"agregado como zona \"{zona_nombre}\"."
            )
            camara_completa = {
                "IdCamara": id_camara, "IdZona": zona["IdZona"], "Zona": zona_nombre,
                "Nombre": f"{nombre_dispositivo}-Canal{canal}", "Marca": marca,
                "TipoConexion": "RTSP", "UrlConexion": canal_info["url"], "Estado": "Activa",
                "TienePTZ": tiene_ptz,
            }
            self.on_camara_agregada(camara_completa)

        self.cargar()

    # ---------------- quitar grabador y sus camaras ----------------
    def quitar(self, id_dispositivo):
        if self.usuario["Rol"] != "Administrador":
            QMessageBox.warning(self.view, "Permiso denegado", "Solo un administrador puede quitar un grabador.")
            return
        dispositivo = self._buscar(id_dispositivo)
        if not dispositivo:
            return

        camaras = dispositivo_dvr_model.camaras_del_dispositivo(id_dispositivo)
        for camara in camaras:
            camara_model.actualizar_estado(camara["IdCamara"], "Inactiva")
            self.on_camara_quitada(camara["Zona"])

        try:
            dispositivo_dvr_model.eliminar(id_dispositivo)
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(self.view, "No se pudo quitar el grabador", str(exc))
            return

        self.cargar()
        self.view.registrar_evento(
            f"[{dispositivo['Nombre']}] Grabador quitado junto con sus {len(camaras)} camara(s)."
        )
