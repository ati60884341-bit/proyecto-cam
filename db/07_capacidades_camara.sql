----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 07_capacidades_camara.sql : capacidades reales por camara (no por
---- marca): hoy solo "tiene motor PTZ" (puede moverse / tiene presets).
----
---- Por que por CAMARA y no por MARCA: una misma marca (Hikvision, Dahua,
---- etc.) vende tanto camaras fijas como domos PTZ - asumir la capacidad
---- por marca haria que el programa ofrezca comandos de mover/preset que
---- la camara real no puede ejecutar (o al reves, los esconda cuando si
---- puede). Aqui cada camara declara lo que tiene de verdad al agregarla.
----
---- Se puede correr sobre una base ya existente (no borra nada):
----   sqlcmd -S localhost -E -C -i db/07_capacidades_camara.sql
----------------------------------------------------------------

USE bd_cam_seguridad;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'cam.Camaras') AND name = N'TienePTZ')
BEGIN
    ALTER TABLE cam.Camaras ADD TienePTZ BIT NOT NULL DEFAULT 0;
END
GO

---- recordado en el grabador para que "Detectar canales nuevos" (que no
---- vuelve a preguntar) use la misma respuesta que se dio al registrarlo
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'cam.DispositivosDVR') AND name = N'CanalesPTZ')
BEGIN
    ALTER TABLE cam.DispositivosDVR ADD CanalesPTZ BIT NOT NULL DEFAULT 0;
END
GO
