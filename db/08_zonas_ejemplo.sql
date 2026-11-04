----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 08_zonas_ejemplo.sql : limpia las 3 camaras RTSP SIMULADAS de la demo
---- escolar (Patio/Estacionamiento/Pasillo, con IPs inventadas que no
---- existen) y deja varias zonas de ejemplo genericas para elegir al
---- agregar una camara real, sin que el nombre choque con las viejas.
----
---- "Cam-Ingreso-01" (la webcam USB, indice 0) NO se toca: a diferencia de
---- las otras 3, esa SI es una camara real que funciona en cualquier PC
---- con webcam (no apunta a una IP inventada) - se usa de verdad para
---- deteccion de gesto/panico y sabotaje, asi que debe seguir activa para
---- cualquiera que instale el programa de cero.
----
---- No borra nada: las 3 camaras simuladas quedan Inactivas (igual que
---- "Quitar camara" desde la pestana Camaras), no se eliminan de la BD.
---- Se puede correr sobre una base ya existente:
----   sqlcmd -S localhost -E -C -i db/08_zonas_ejemplo.sql
----------------------------------------------------------------

USE bd_cam_seguridad;
GO

---- 1) desactiva las 3 camaras RTSP SIMULADAS de 03_seed.sql (por nombre,
---- para no tocar ninguna camara real que el usuario haya agregado) ----
UPDATE cam.Camaras SET Estado = N'Inactiva'
WHERE Nombre IN (N'Cam-Patio-01', N'Cam-Estacionamiento-01', N'Cam-Pasillo-01')
  AND Estado = N'Activa';
GO

---- 2) renombra esas 4 zonas a nombres claramente de ejemplo, para que no
---- se confundan con una zona real que el usuario escriba despues (ej. si
---- escribe "Patio" para su propia camara, ya no choca con la demo) ----
UPDATE cam.Zonas SET Nombre = N'Zona de prueba 1' WHERE Nombre = N'Ingreso';
UPDATE cam.Zonas SET Nombre = N'Zona de prueba 2' WHERE Nombre = N'Patio';
UPDATE cam.Zonas SET Nombre = N'Zona de prueba 3' WHERE Nombre = N'Estacionamiento';
UPDATE cam.Zonas SET Nombre = N'Zona de prueba 4' WHERE Nombre = N'Pasillo';
GO

---- 3) zonas genericas adicionales, sin camara todavia, listas para elegir
---- en el desplegable "Zona" al agregar una camara real ----
INSERT INTO cam.Zonas (Nombre, Descripcion)
SELECT v.Nombre, v.Descripcion
FROM (VALUES
    (N'Recepcion',       N'Area de recepcion / mostrador'),
    (N'Almacen',         N'Deposito / bodega'),
    (N'Oficina principal', N'Oficina administrativa'),
    (N'Entrada trasera',   N'Puerta/acceso de servicio'),
    (N'Cochera',          N'Garaje / cochera'),
    (N'Pasillo 2',         N'Segundo pasillo de circulacion')
) AS v(Nombre, Descripcion)
WHERE NOT EXISTS (SELECT 1 FROM cam.Zonas z WHERE z.Nombre = v.Nombre);
GO

SELECT IdZona, Nombre, Descripcion FROM cam.Zonas ORDER BY IdZona;
GO
