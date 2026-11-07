----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 10_perfiles_sitio.sql : pestana "NVR / DVR" - perfiles de sitio
----
---- Guarda, por taller/cliente, los datos tipicos de su grabador (IP,
---- puerto, marca, usuario, nombre de la red del router portatil) para
---- no tener que escribirlos de memoria en cada visita - NO guarda la
---- clave del grabador (eso se sigue escribiendo a mano cada vez).
----
---- Se puede correr sobre una base ya existente (no borra nada, usa
---- IF NOT EXISTS). Ejecutar una sola vez:
----   sqlcmd -S localhost -E -C -i db/10_perfiles_sitio.sql
----------------------------------------------------------------

USE bd_cam_seguridad;
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = N'PerfilesSitio' AND schema_id = SCHEMA_ID(N'cam'))
BEGIN
    CREATE TABLE cam.PerfilesSitio (
        IdPerfil          INT IDENTITY(1,1) PRIMARY KEY,
        Nombre            NVARCHAR(100) NOT NULL,
        IpDvrTipica       NVARCHAR(50)  NULL,
        PuertoTipico      INT NOT NULL DEFAULT 554,
        MarcaTipica       NVARCHAR(30)  NULL CHECK (MarcaTipica IS NULL OR MarcaTipica IN (N'Hikvision', N'Dahua')),
        UsuarioTipico     NVARCHAR(50)  NOT NULL DEFAULT N'admin',
        NombreRedRouter   NVARCHAR(100) NULL,
        Notas             NVARCHAR(400) NULL,
        FechaCreacion     DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END
GO
