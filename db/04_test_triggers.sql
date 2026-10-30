USE bd_cam_seguridad;
GO

----test 1: incidencia de panico -> debe crear AlertasPanico automaticamente----
INSERT INTO cam.Incidencias (IdZona, Tipo, Descripcion) VALUES (1, N'Panico', N'Prueba de panico silencioso');
SELECT * FROM cam.AlertasPanico;

----test 2: insertar evidencia en zona 1 (Ingreso, con panico activo) y tratar de borrarla -> debe fallar----
INSERT INTO cam.Evidencias (IdZona, RutaArchivo, TipoArchivo, HashSHA256)
VALUES (1, N'evidencias/test.jpg', N'Foto', REPLICATE('a', 64));

BEGIN TRY
    DELETE FROM cam.Evidencias WHERE IdZona = 1;
    PRINT 'ERROR: el borrado NO debio permitirse';
END TRY
BEGIN CATCH
    PRINT 'OK: borrado bloqueado por cadena de custodia -> ' + ERROR_MESSAGE();
END CATCH

----test 3: atender la alerta de panico, luego el borrado si debe funcionar----
UPDATE cam.AlertasPanico SET Atendida = 1 WHERE IdZona = 1;
DELETE FROM cam.Evidencias WHERE IdZona = 1;
SELECT * FROM cam.EvidenciasEliminadas;

----test 4: 3 sabotajes seguidos en zona 2 -> debe generar escalamiento critico automatico----
INSERT INTO cam.Incidencias (IdZona, Tipo, Descripcion) VALUES (2, N'Sabotaje', N'Camara tapada');
INSERT INTO cam.Incidencias (IdZona, Tipo, Descripcion) VALUES (2, N'Sabotaje', N'Camara tapada de nuevo');
INSERT INTO cam.Incidencias (IdZona, Tipo, Descripcion) VALUES (2, N'Sabotaje', N'Camara movida');
SELECT IdIncidencia, IdZona, Tipo, Severidad, Descripcion FROM cam.Incidencias WHERE IdZona = 2;

----test 5: marcar una incidencia como atendida -> debe loguearse en HistorialIncidencias----
UPDATE cam.Incidencias SET Atendida = 1, FechaAtencion = SYSDATETIME() WHERE IdIncidencia = 1;
SELECT * FROM cam.HistorialIncidencias;

----test 6: abrir y cerrar un turno -> debe loguearse en HistorialTurnos----
INSERT INTO cam.Turnos (IdUsuario) VALUES (2);
DECLARE @idTurno INT = SCOPE_IDENTITY();
WAITFOR DELAY '00:00:01';
UPDATE cam.Turnos SET Estado = N'Cerrado', FechaFin = SYSDATETIME() WHERE IdTurno = @idTurno;
SELECT * FROM cam.HistorialTurnos;
GO
