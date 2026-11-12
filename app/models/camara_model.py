from app.database.conexion_bd import query, execute


def listar(incluir_inactivas=False):
    """Por defecto solo trae camaras Activas: una camara "quitada" (Estado =
    Inactiva) no debe reaparecer en el Centro de Monitoreo ni en la lista de
    la pestana Camaras, para que el administrador pueda agregar una nueva
    de una vez. incluir_inactivas=True es para auditoria/depuracion."""
    filtro = "" if incluir_inactivas else "WHERE c.Estado = N'Activa'"
    # IdDispositivo/Canal/Dispositivo*: a que DVR/NVR pertenece la camara (NULL
    # si es independiente) - el Centro de Monitoreo las agrupa por grabador
    camaras = query(
        "SELECT c.IdCamara, c.IdZona, z.Nombre AS Zona, c.Nombre, c.Marca, c.TipoConexion, c.UrlConexion, "
        "c.Estado, c.TienePTZ, c.IdDispositivo, c.Canal, "
        "d.Nombre AS Dispositivo, d.Tipo AS DispositivoTipo, d.Marca AS DispositivoMarca, d.IP AS DispositivoIP "
        "FROM cam.Camaras c JOIN cam.Zonas z ON z.IdZona = c.IdZona "
        f"LEFT JOIN cam.DispositivosDVR d ON d.IdDispositivo = c.IdDispositivo {filtro} "
        "ORDER BY c.IdDispositivo, c.Canal, c.IdCamara"
    )
    # "Clave" identifica a cada camara en el Centro de Monitoreo (un recuadro
    # por camara): es su nombre, salvo que datos viejos repitan un nombre
    usadas = set()
    for c in camaras:
        clave = c["Nombre"] if c["Nombre"] not in usadas else f"{c['Nombre']} #{c['IdCamara']}"
        usadas.add(clave)
        c["Clave"] = clave
    return camaras


def actualizar_estado(id_camara, estado):
    execute("UPDATE cam.Camaras SET Estado = ? WHERE IdCamara = ?", (estado, id_camara))


def crear(id_zona, nombre, marca, tipo_conexion, url_conexion, id_dispositivo=None, canal=None, tiene_ptz=False):
    """Registra una camara nueva. Cualquier marca es compatible: RTSP sirve
    para Hikvision/Dahua/Tapo/cualquier IP generica, USB para webcams.
    id_dispositivo/canal solo se usan cuando la camara viene de un canal de
    la pestana "NVR / DVR" (alta masiva); para una camara independiente
    quedan en NULL. tiene_ptz es una capacidad POR CAMARA, no por marca:
    una misma marca vende tanto domos PTZ como camaras fijas."""
    return execute(
        "INSERT INTO cam.Camaras (IdZona, Nombre, Marca, TipoConexion, UrlConexion, IdDispositivo, Canal, TienePTZ) "
        "OUTPUT INSERTED.IdCamara VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (id_zona, nombre, marca, tipo_conexion, url_conexion, id_dispositivo, canal, tiene_ptz),
        return_id=True,
    )
