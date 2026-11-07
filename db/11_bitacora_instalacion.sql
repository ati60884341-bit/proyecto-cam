----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 11_bitacora_instalacion.sql : pestana "NVR / DVR" - bitacora de
---- instalacion por grabador, compartida entre todos los tecnicos (queda
---- en la base central, no en la PC de cada uno)
----
---- Ejemplo de uso: "Este DVR necesita el puerto 8000, no el 554" o
---- "La red del taller tiene aislamiento de clientes por WiFi, conectar
---- por cable" - para que el siguiente tecnico no repita el mismo
---- diagnostico desde cero.
----
---- Se puede correr sobre una base ya existente (no borra nada, usa
---- IF NOT EXISTS). Ejecutar una sola vez:
----   sqlcmd -S localhost -E -C -i db/11_bitacora_instalacion.sql
----------------------------------------------------------------

USE bd_cam_seguridad;
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = N'BitacoraInstalacion' AND schema_id = SCHEMA_ID(N'cam'))
BEGIN
    CREATE TABLE cam.BitacoraInstalacion (
        IdNota         INT IDENTITY(1,1) PRIMARY KEY,
        -- NULL = el dispositivo ya se quito (ver DvrController.quitar); la
        -- nota se conserva igual, solo pierde su vinculo al grabador
        IdDispositivo  INT NULL,
        IdUsuario      INT NULL,
        Texto          NVARCHAR(500) NOT NULL,
        Fecha          DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        CONSTRAINT FK_BitacoraInstalacion_DispositivosDVR
            FOREIGN KEY (IdDispositivo) REFERENCES cam.DispositivosDVR(IdDispositivo) ON DELETE SET NULL,
        CONSTRAINT FK_BitacoraInstalacion_Usuarios
            FOREIGN KEY (IdUsuario) REFERENCES cam.Usuarios(IdUsuario) ON DELETE SET NULL
    );
END
GO
