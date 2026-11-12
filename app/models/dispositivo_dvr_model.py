from app.database.conexion_bd import query, query_one, execute


def listar():
    return query(
        "SELECT d.IdDispositivo, d.Nombre, d.Tipo, d.Marca, d.IP, d.Puerto, d.Usuario, d.Clave, d.CantidadCanales, "
        "(SELECT COUNT(*) FROM cam.Camaras c WHERE c.IdDispositivo = d.IdDispositivo AND c.Estado = N'Activa') AS CamarasActivas "
        "FROM cam.DispositivosDVR d ORDER BY d.IdDispositivo"
    )


def obtener(id_dispositivo):
    return query_one(
        "SELECT IdDispositivo, Nombre, Tipo, Marca, IP, Puerto, Usuario, Clave, CantidadCanales, CanalesPTZ "
        "FROM cam.DispositivosDVR WHERE IdDispositivo = ?",
        (id_dispositivo,),
    )


def crear(nombre, marca, ip, puerto, usuario, clave, cantidad_canales, canales_ptz=False, tipo="DVR"):
    return execute(
        "INSERT INTO cam.DispositivosDVR (Nombre, Tipo, Marca, IP, Puerto, Usuario, Clave, CantidadCanales, CanalesPTZ) "
        "OUTPUT INSERTED.IdDispositivo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (nombre, tipo, marca, ip, puerto, usuario, clave, cantidad_canales, canales_ptz),
        return_id=True,
    )


def eliminar(id_dispositivo):
    """La app debe marcar Inactivas (y detener los hilos de) las camaras de
    este dispositivo ANTES de llamar a esto. La FK es ON DELETE SET NULL:
    las camaras no se borran, solo dejan de estar ligadas al dispositivo."""
    execute("DELETE FROM cam.DispositivosDVR WHERE IdDispositivo = ?", (id_dispositivo,))


def canales_registrados(id_dispositivo):
    """Numeros de canal que ya tienen una camara Activa para este
    dispositivo, para no duplicar al volver a "Detectar canales"."""
    filas = query(
        "SELECT Canal FROM cam.Camaras WHERE IdDispositivo = ? AND Estado = N'Activa' AND Canal IS NOT NULL",
        (id_dispositivo,),
    )
    return {f["Canal"] for f in filas}


def camaras_del_dispositivo(id_dispositivo):
    return query(
        "SELECT c.IdCamara, c.Nombre, c.Canal, z.Nombre AS Zona FROM cam.Camaras c "
        "JOIN cam.Zonas z ON z.IdZona = c.IdZona "
        "WHERE c.IdDispositivo = ? AND c.Estado = N'Activa' ORDER BY c.Canal",
        (id_dispositivo,),
    )
