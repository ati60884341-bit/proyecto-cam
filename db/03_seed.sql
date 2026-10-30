----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 03_seed.sql : datos iniciales para la demo
----------------------------------------------------------------

USE bd_cam_seguridad;
GO

----zonas de la maqueta----
INSERT INTO cam.Zonas (Nombre, Descripcion) VALUES
    (N'Ingreso', N'Entrada principal del local'),
    (N'Patio', N'Patio interior'),
    (N'Estacionamiento', N'Zona de parqueo vehicular'),
    (N'Pasillo', N'Pasillo de circulacion interna');
GO

----camaras: una webcam USB real para la demo en vivo, y camaras RTSP simuladas de otras marcas----
INSERT INTO cam.Camaras (IdZona, Nombre, Marca, TipoConexion, UrlConexion, Estado) VALUES
    ((SELECT IdZona FROM cam.Zonas WHERE Nombre = N'Ingreso'),          N'Cam-Ingreso-01',          N'WebcamUSB', N'USB',  N'0', N'Activa'),
    ((SELECT IdZona FROM cam.Zonas WHERE Nombre = N'Patio'),            N'Cam-Patio-01',            N'Hikvision', N'RTSP', N'rtsp://usuario:clave@192.168.1.101:554/Streaming/Channels/101', N'Activa'),
    ((SELECT IdZona FROM cam.Zonas WHERE Nombre = N'Estacionamiento'),  N'Cam-Estacionamiento-01',  N'Dahua',     N'RTSP', N'rtsp://usuario:clave@192.168.1.102:554/cam/realmonitor?channel=1&subtype=0', N'Activa'),
    ((SELECT IdZona FROM cam.Zonas WHERE Nombre = N'Pasillo'),          N'Cam-Pasillo-01',          N'Tapo',      N'RTSP', N'rtsp://usuario:clave@192.168.1.103:554/stream1', N'Activa');
GO

----usuarios: un administrador y un vigilante. clave de ambos: "123456" (hash SHA-256)----
----hash SHA-256 de "123456" = 8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92----
INSERT INTO cam.Usuarios (NombreCompleto, NombreUsuario, ClaveHash, Rol) VALUES
    (N'Administrador General', N'admin',    N'8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', N'Administrador'),
    (N'Juan Vigilante',        N'vigilante', N'8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', N'Vigilante');
GO

SELECT * FROM cam.Zonas;
SELECT * FROM cam.Camaras;
SELECT * FROM cam.Usuarios;
GO
