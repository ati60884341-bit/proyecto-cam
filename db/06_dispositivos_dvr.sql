----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 06_dispositivos_dvr.sql : pestana "NVR / DVR" (alta masiva de canales)
----
---- Se puede correr sobre una base ya existente (no borra nada, usa
---- IF NOT EXISTS). Ejecutar una sola vez:
----   sqlcmd -S localhost -E -C -i db/06_dispositivos_dvr.sql
----------------------------------------------------------------

USE bd_cam_seguridad;
GO

----------------------------------------------------------------
---- Tabla: DispositivosDVR (el DVR/NVR fisico: una fila por equipo,
---- no por camara - un DVR de 8 canales son 8 camaras bajo 1 dispositivo)
----------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = N'DispositivosDVR' AND schema_id = SCHEMA_ID(N'cam'))
BEGIN
    CREATE TABLE cam.DispositivosDVR (
        IdDispositivo   INT IDENTITY(1,1) PRIMARY KEY,
        Nombre          NVARCHAR(100) NOT NULL,
        Marca           NVARCHAR(30)  NOT NULL CHECK (Marca IN (N'Hikvision', N'Dahua')),
        IP              NVARCHAR(50)  NOT NULL,
        Puerto          INT NOT NULL DEFAULT 554,
        Usuario         NVARCHAR(50)  NOT NULL DEFAULT N'admin',
        Clave           NVARCHAR(100) NULL,
        CantidadCanales INT NOT NULL DEFAULT 4,
        FechaRegistro   DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END
GO

----------------------------------------------------------------
---- cam.Camaras: de que dispositivo y canal viene (NULL = camara
---- independiente, agregada a mano desde la pestana "Camaras")
----------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'cam.Camaras') AND name = N'IdDispositivo')
BEGIN
    ALTER TABLE cam.Camaras ADD IdDispositivo INT NULL;
    -- ON DELETE SET NULL: al quitar el dispositivo, las camaras no se
    -- borran solas (la app las marca Inactiva y detiene sus hilos primero)
    ALTER TABLE cam.Camaras ADD CONSTRAINT FK_Camaras_DispositivosDVR
        FOREIGN KEY (IdDispositivo) REFERENCES cam.DispositivosDVR(IdDispositivo) ON DELETE SET NULL;
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'cam.Camaras') AND name = N'Canal')
BEGIN
    ALTER TABLE cam.Camaras ADD Canal INT NULL;  -- numero de canal dentro del DVR/NVR (1, 2, 3...)
END
GO
