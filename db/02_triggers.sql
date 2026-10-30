----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 02_triggers.sql : triggers de auditoria y reglas de negocio
----------------------------------------------------------------

USE bd_cam_seguridad;
GO

----------------------------------------------------------------
---- TRIGGER 1: historial de cambios en Incidencias (AFTER UPDATE)
---- Registra cada vez que una incidencia cambia de estado o severidad
----------------------------------------------------------------
CREATE OR ALTER TRIGGER cam.trg_HistorialIncidencias
ON cam.Incidencias
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO cam.HistorialIncidencias
        (IdIncidencia, AtendidaAnterior, AtendidaNueva, SeveridadAnterior, SeveridadNueva)
    SELECT
        i.IdIncidencia,
        d.Atendida,
        i.Atendida,
        d.Severidad,
        i.Severidad
    FROM inserted AS i
    INNER JOIN deleted AS d
        ON i.IdIncidencia = d.IdIncidencia
    WHERE i.Atendida <> d.Atendida OR i.Severidad <> d.Severidad;
END;
GO

----------------------------------------------------------------
---- TRIGGER 2: registro automatico de incidencias nuevas (AFTER INSERT)
---- Si la incidencia es de tipo 'Panico', genera automaticamente la
---- alerta de panico silencioso con bloqueo de borrado de evidencias.
----------------------------------------------------------------
CREATE OR ALTER TRIGGER cam.trg_RegistroNuevaIncidencia
ON cam.Incidencias
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO cam.AlertasPanico (IdIncidencia, IdZona, BloqueoBorrado)
    SELECT
        i.IdIncidencia,
        i.IdZona,
        1
    FROM inserted AS i
    WHERE i.Tipo = N'Panico';
END;
GO

----------------------------------------------------------------
---- TRIGGER 3: cadena de custodia legal (INSTEAD OF DELETE)
---- Bloquea el borrado de evidencias si la zona tiene una alerta de
---- panico activa (BloqueoBorrado = 1 y no atendida); en caso contrario
---- permite el borrado pero conserva un respaldo en EvidenciasEliminadas.
----------------------------------------------------------------
CREATE OR ALTER TRIGGER cam.trg_BloqueoBorradoEvidencias
ON cam.Evidencias
INSTEAD OF DELETE
AS
BEGIN
    SET NOCOUNT ON;

    ----si alguna evidencia a borrar pertenece a una zona con alerta de panico activa, se cancela todo el borrado----
    IF EXISTS (
        SELECT 1
        FROM deleted AS d
        INNER JOIN cam.AlertasPanico AS a
            ON a.IdZona = d.IdZona
        WHERE a.BloqueoBorrado = 1 AND a.Atendida = 0
    )
    BEGIN
        RAISERROR(N'No se puede borrar: existe una alerta de panico activa que protege la evidencia (cadena de custodia legal).', 16, 1);
        RETURN;
    END

    INSERT INTO cam.EvidenciasEliminadas (IdEvidencia, RutaArchivo, HashSHA256, IdUsuario)
    SELECT IdEvidencia, RutaArchivo, HashSHA256, IdUsuario
    FROM deleted;

    DELETE FROM cam.Evidencias
    WHERE IdEvidencia IN (SELECT IdEvidencia FROM deleted);
END;
GO

----------------------------------------------------------------
---- TRIGGER 4: escalamiento por sabotajes repetidos (AFTER INSERT)
---- Si una zona acumula 3 o mas incidencias de sabotaje en los ultimos
---- 10 minutos, se crea una incidencia adicional de severidad Critica.
----------------------------------------------------------------
CREATE OR ALTER TRIGGER cam.trg_EscalamientoSabotajeRepetido
ON cam.Incidencias
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO cam.Incidencias (IdZona, IdCamara, IdTurno, Tipo, Severidad, Descripcion)
    SELECT
        i.IdZona,
        i.IdCamara,
        i.IdTurno,
        N'Sabotaje',
        N'Critica',
        N'Escalamiento automatico: 3 o mas sabotajes en 10 minutos'
    FROM inserted AS i
    WHERE i.Tipo = N'Sabotaje'
      AND (
            SELECT COUNT(*)
            FROM cam.Incidencias AS x
            WHERE x.IdZona = i.IdZona
              AND x.Tipo = N'Sabotaje'
              AND x.FechaHora >= DATEADD(MINUTE, -10, SYSDATETIME())
          ) >= 3
      AND NOT EXISTS (
            SELECT 1 FROM cam.Incidencias AS y
            WHERE y.IdZona = i.IdZona
              AND y.Severidad = N'Critica'
              AND y.Descripcion LIKE N'Escalamiento automatico%'
              AND y.FechaHora >= DATEADD(MINUTE, -10, SYSDATETIME())
          );
END;
GO

----------------------------------------------------------------
---- TRIGGER 5: duracion de turno al cerrarse (AFTER UPDATE)
---- Cuando un turno cambia a Estado = 'Cerrado', calcula su duracion
---- en minutos y la registra en HistorialTurnos.
----------------------------------------------------------------
CREATE OR ALTER TRIGGER cam.trg_CierreTurno
ON cam.Turnos
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO cam.HistorialTurnos (IdTurno, IdUsuario, DuracionMinutos)
    SELECT
        i.IdTurno,
        i.IdUsuario,
        DATEDIFF(MINUTE, i.FechaInicio, ISNULL(i.FechaFin, SYSDATETIME()))
    FROM inserted AS i
    INNER JOIN deleted AS d
        ON i.IdTurno = d.IdTurno
    WHERE i.Estado = N'Cerrado' AND d.Estado <> N'Cerrado';
END;
GO
