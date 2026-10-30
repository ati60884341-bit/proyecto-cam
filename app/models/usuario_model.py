import hashlib
from app.database.conexion_bd import query, query_one, execute


def hash_clave(texto_plano):
    return hashlib.sha256(texto_plano.encode("utf-8")).hexdigest()


def autenticar(nombre_usuario, clave_plana):
    clave_hash = hash_clave(clave_plana)
    return query_one(
        "SELECT IdUsuario, NombreCompleto, NombreUsuario, Rol FROM cam.Usuarios "
        "WHERE NombreUsuario = ? AND ClaveHash = ? AND Activo = 1",
        (nombre_usuario, clave_hash),
    )


def listar():
    return query("SELECT IdUsuario, NombreCompleto, NombreUsuario, Rol, Activo FROM cam.Usuarios ORDER BY NombreCompleto")


def crear(nombre_completo, nombre_usuario, clave_plana, rol):
    return execute(
        "INSERT INTO cam.Usuarios (NombreCompleto, NombreUsuario, ClaveHash, Rol) "
        "OUTPUT INSERTED.IdUsuario VALUES (?, ?, ?, ?)",
        (nombre_completo, nombre_usuario, hash_clave(clave_plana), rol),
        return_id=True,
    )


def desactivar(id_usuario):
    execute("UPDATE cam.Usuarios SET Activo = 0 WHERE IdUsuario = ?", (id_usuario,))
