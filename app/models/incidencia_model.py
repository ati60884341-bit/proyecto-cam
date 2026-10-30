from app.database.conexion_bd import query, execute


def crear(id_zona, tipo, descripcion, id_camara=None, id_turno=None, severidad="Normal"):
    # Incidencias tiene triggers AFTER INSERT: SQL Server no permite
    # "OUTPUT INSERTED.col" simple en una tabla con un trigger para la misma
    # operacion, hay que mandarlo a una tabla variable y leerlo de ahi
    return execute(
        "SET NOCOUNT ON; "
        "DECLARE @out TABLE(id INT); "
        "INSERT INTO cam.Incidencias (IdZona, IdCamara, IdTurno, Tipo, Severidad, Descripcion) "
        "OUTPUT INSERTED.IdIncidencia INTO @out "
        "VALUES (?, ?, ?, ?, ?, ?); "
        "SELECT id FROM @out;",
        (id_zona, id_camara, id_turno, tipo, severidad, descripcion),
        return_id=True,
    )


def listar(limite=200):
    return query(
        "SELECT TOP (?) i.IdIncidencia, z.Nombre AS Zona, i.Tipo, i.Severidad, i.Descripcion, "
        "i.FechaHora, i.Atendida "
        "FROM cam.Incidencias i JOIN cam.Zonas z ON z.IdZona = i.IdZona "
        "ORDER BY i.FechaHora DESC",
        (limite,),
    )


def atender(id_incidencia):
    execute(
        "UPDATE cam.Incidencias SET Atendida = 1, FechaAtencion = SYSDATETIME() WHERE IdIncidencia = ?",
        (id_incidencia,),
    )


def conteo_por_tipo():
    return query("SELECT Tipo, COUNT(*) AS Total FROM cam.Incidencias GROUP BY Tipo ORDER BY Total DESC")


def conteo_por_zona():
    return query(
        "SELECT z.Nombre AS Zona, COUNT(*) AS Total FROM cam.Incidencias i "
        "JOIN cam.Zonas z ON z.IdZona = i.IdZona GROUP BY z.Nombre ORDER BY Total DESC"
    )
