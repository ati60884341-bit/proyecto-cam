from app.database.conexion_bd import execute, query


def registrar(id_usuario, confirmado, id_turno=None):
    execute(
        "INSERT INTO cam.FatigaRegistros (IdUsuario, IdTurno, Confirmado) VALUES (?, ?, ?)",
        (id_usuario, id_turno, confirmado),
    )


def listar(limite=100):
    return query(
        "SELECT TOP (?) f.IdRegistro, u.NombreCompleto AS Usuario, f.Confirmado, f.FechaHora "
        "FROM cam.FatigaRegistros f JOIN cam.Usuarios u ON u.IdUsuario = f.IdUsuario "
        "ORDER BY f.FechaHora DESC",
        (limite,),
    )
