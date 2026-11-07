from app.database.conexion_bd import query, execute


def agregar(id_dispositivo, id_usuario, texto):
    return execute(
        "INSERT INTO cam.BitacoraInstalacion (IdDispositivo, IdUsuario, Texto) "
        "OUTPUT INSERTED.IdNota VALUES (?, ?, ?)",
        (id_dispositivo, id_usuario, texto),
        return_id=True,
    )


def listar_por_dispositivo(id_dispositivo):
    return query(
        "SELECT b.IdNota, b.Texto, b.Fecha, u.NombreCompleto "
        "FROM cam.BitacoraInstalacion b LEFT JOIN cam.Usuarios u ON u.IdUsuario = b.IdUsuario "
        "WHERE b.IdDispositivo = ? ORDER BY b.Fecha DESC",
        (id_dispositivo,),
    )
