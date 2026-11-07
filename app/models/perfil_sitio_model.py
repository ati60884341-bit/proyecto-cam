from app.database.conexion_bd import query, query_one, execute


def listar():
    return query(
        "SELECT IdPerfil, Nombre, IpDvrTipica, PuertoTipico, MarcaTipica, UsuarioTipico, "
        "NombreRedRouter, Notas FROM cam.PerfilesSitio ORDER BY Nombre"
    )


def obtener(id_perfil):
    return query_one(
        "SELECT IdPerfil, Nombre, IpDvrTipica, PuertoTipico, MarcaTipica, UsuarioTipico, "
        "NombreRedRouter, Notas FROM cam.PerfilesSitio WHERE IdPerfil = ?",
        (id_perfil,),
    )


def crear(nombre, ip_dvr_tipica, puerto_tipico, marca_tipica, usuario_tipico, nombre_red_router, notas):
    return execute(
        "INSERT INTO cam.PerfilesSitio (Nombre, IpDvrTipica, PuertoTipico, MarcaTipica, UsuarioTipico, "
        "NombreRedRouter, Notas) OUTPUT INSERTED.IdPerfil VALUES (?, ?, ?, ?, ?, ?, ?)",
        (nombre, ip_dvr_tipica, puerto_tipico, marca_tipica, usuario_tipico, nombre_red_router, notas),
        return_id=True,
    )


def eliminar(id_perfil):
    execute("DELETE FROM cam.PerfilesSitio WHERE IdPerfil = ?", (id_perfil,))
