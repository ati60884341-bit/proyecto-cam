from app.database.conexion_bd import query, execute


def listar(incluir_inactivas=False):
    """Por defecto solo trae camaras Activas: una camara "quitada" (Estado =
    Inactiva) no debe reaparecer en el Centro de Monitoreo ni en la lista de
    la pestana Camaras, para que el administrador pueda agregar una nueva
    de una vez. incluir_inactivas=True es para auditoria/depuracion."""
    filtro = "" if incluir_inactivas else "WHERE c.Estado = N'Activa'"
    return query(
        "SELECT c.IdCamara, c.IdZona, z.Nombre AS Zona, c.Nombre, c.Marca, c.TipoConexion, c.UrlConexion, c.Estado "
        f"FROM cam.Camaras c JOIN cam.Zonas z ON z.IdZona = c.IdZona {filtro} ORDER BY c.IdZona"
    )


def actualizar_estado(id_camara, estado):
    execute("UPDATE cam.Camaras SET Estado = ? WHERE IdCamara = ?", (estado, id_camara))


def crear(id_zona, nombre, marca, tipo_conexion, url_conexion):
    """Registra una camara nueva. Cualquier marca es compatible: RTSP sirve
    para Hikvision/Dahua/Tapo/cualquier IP generica, USB para webcams."""
    return execute(
        "INSERT INTO cam.Camaras (IdZona, Nombre, Marca, TipoConexion, UrlConexion) "
        "OUTPUT INSERTED.IdCamara VALUES (?, ?, ?, ?, ?)",
        (id_zona, nombre, marca, tipo_conexion, url_conexion),
        return_id=True,
    )
