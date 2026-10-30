from app.database.conexion_bd import query, query_one, execute


def listar():
    return query("SELECT IdZona, Nombre, Descripcion FROM cam.Zonas ORDER BY IdZona")


def obtener_por_nombre(nombre):
    return query_one("SELECT IdZona, Nombre, Descripcion FROM cam.Zonas WHERE Nombre = ?", (nombre,))


def obtener_o_crear(nombre, descripcion=None):
    """Usado al agregar una camara: si la zona (ej. un area nueva de la
    maqueta) aun no existe, se crea en el momento."""
    zona = obtener_por_nombre(nombre)
    if zona:
        return zona
    nuevo_id = execute(
        "INSERT INTO cam.Zonas (Nombre, Descripcion) OUTPUT INSERTED.IdZona VALUES (?, ?)",
        (nombre, descripcion),
        return_id=True,
    )
    return {"IdZona": nuevo_id, "Nombre": nombre, "Descripcion": descripcion}
