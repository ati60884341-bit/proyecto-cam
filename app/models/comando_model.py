from app.database.conexion_bd import execute, query


def registrar(id_usuario, comando, resultado):
    execute(
        "INSERT INTO cam.ComandosVoz (IdUsuario, Comando, Resultado) VALUES (?, ?, ?)",
        (id_usuario, comando, resultado),
    )


def listar(limite=100):
    return query(
        "SELECT TOP (?) c.IdComando, u.NombreCompleto AS Usuario, c.Comando, c.Resultado, c.FechaHora "
        "FROM cam.ComandosVoz c LEFT JOIN cam.Usuarios u ON u.IdUsuario = c.IdUsuario "
        "ORDER BY c.FechaHora DESC",
        (limite,),
    )
