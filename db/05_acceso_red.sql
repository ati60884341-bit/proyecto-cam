----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 05_acceso_red.sql : login SQL para que otras laptops (fuera del
---- dominio de Windows de este servidor) se conecten por red.
----
---- REQUISITO PREVIO (hacerlo una sola vez, a mano, en este servidor):
----   1. SQL Server Management Studio -> clic derecho en el servidor ->
----      Properties -> Security -> marcar "SQL Server and Windows
----      Authentication mode" (en vez de solo "Windows Authentication
----      mode"). Esto habilita logins con usuario/clave ademas de los de
----      Windows.
----   2. Reiniciar el servicio "SQL Server (MSSQLSERVER)" (en
----      services.msc, o "Restart" en SSMS) para que el cambio tome
----      efecto. Esto corta por un instante cualquier conexion activa:
----      hacerlo fuera de horario de uso.
----   3. En el Firewall de Windows de este servidor, permitir conexiones
----      entrantes al puerto 1433/TCP (SQL Server Configuration Manager
----      -> Protocolos de BDCAMSEGURIDAD/MSSQLSERVER -> TCP/IP habilitado).
----
---- Con eso hecho, correr este script UNA vez (cambiando la clave de mas
---- abajo primero) para crear el login que usaran las demas laptops.
----------------------------------------------------------------

USE master;
GO

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'cam_app')
BEGIN
    -- CAMBIAR 'CAMBIAR_ESTA_CLAVE_123!' por una clave propia antes de ejecutar
    CREATE LOGIN cam_app WITH PASSWORD = N'CAMBIAR_ESTA_CLAVE_123!', CHECK_POLICY = ON;
END
GO

USE bd_cam_seguridad;
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'cam_app')
BEGIN
    CREATE USER cam_app FOR LOGIN cam_app;
END
GO

-- permisos minimos: la app solo lee/escribe filas (los triggers y el
-- esquema cam ya estan creados por 01_schema.sql/02_triggers.sql, no
-- necesita permisos de DDL)
ALTER ROLE db_datareader ADD MEMBER cam_app;
ALTER ROLE db_datawriter ADD MEMBER cam_app;
GO

PRINT 'Login cam_app listo. En cada laptop que se conecte por red, defina estas variables de entorno antes de abrir ProyectoCAM.exe:';
PRINT '  CAM_DB_SERVER=<IP de este servidor>';
PRINT '  CAM_DB_USER=cam_app';
PRINT '  CAM_DB_PASSWORD=<la clave que puso arriba>';
GO
