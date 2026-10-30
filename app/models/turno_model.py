from app.database.conexion_bd import query, query_one, execute


def abrir(id_usuario):
    return execute(
        "INSERT INTO cam.Turnos (IdUsuario) OUTPUT INSERTED.IdTurno VALUES (?)",
        (id_usuario,), return_id=True,
    )


def cerrar(id_turno):
    execute(
        "UPDATE cam.Turnos SET Estado = N'Cerrado', FechaFin = SYSDATETIME() WHERE IdTurno = ?",
        (id_turno,),
    )


def turno_abierto(id_usuario):
    return query_one(
        "SELECT TOP 1 IdTurno, FechaInicio FROM cam.Turnos "
        "WHERE IdUsuario = ? AND Estado = N'Abierto' ORDER BY FechaInicio DESC",
        (id_usuario,),
    )


def listar_historial():
    return query(
        "SELECT h.IdTurno, u.NombreCompleto AS Usuario, h.DuracionMinutos, h.FechaCierre "
        "FROM cam.HistorialTurnos h JOIN cam.Usuarios u ON u.IdUsuario = h.IdUsuario "
        "ORDER BY h.FechaCierre DESC"
    )
