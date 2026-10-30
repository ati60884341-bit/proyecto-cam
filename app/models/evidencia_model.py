import pyodbc
from app.database.conexion_bd import query, execute


def crear(id_zona, ruta_archivo, tipo_archivo, hash_sha256, id_usuario=None, id_incidencia=None):
    return execute(
        "INSERT INTO cam.Evidencias (IdIncidencia, IdZona, IdUsuario, RutaArchivo, TipoArchivo, HashSHA256) "
        "OUTPUT INSERTED.IdEvidencia VALUES (?, ?, ?, ?, ?, ?)",
        (id_incidencia, id_zona, id_usuario, ruta_archivo, tipo_archivo, hash_sha256),
        return_id=True,
    )


def listar(limite=200):
    return query(
        "SELECT TOP (?) e.IdEvidencia, z.Nombre AS Zona, e.TipoArchivo, e.RutaArchivo, e.HashSHA256, "
        "e.FechaCaptura, u.NombreCompleto AS Usuario "
        "FROM cam.Evidencias e JOIN cam.Zonas z ON z.IdZona = e.IdZona "
        "LEFT JOIN cam.Usuarios u ON u.IdUsuario = e.IdUsuario "
        "ORDER BY e.FechaCaptura DESC",
        (limite,),
    )


def eliminar(id_evidencia):
    """Returns (ok: bool, mensaje: str). A trigger blocks this while a panic alert is active."""
    try:
        execute("DELETE FROM cam.Evidencias WHERE IdEvidencia = ?", (id_evidencia,))
        return True, "Evidencia eliminada correctamente."
    except pyodbc.Error as exc:
        return False, str(exc)
