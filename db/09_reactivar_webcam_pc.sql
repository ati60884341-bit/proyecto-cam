----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 09_reactivar_webcam_pc.sql : corrige 08_zonas_ejemplo.sql
----
---- 08_zonas_ejemplo.sql desactivo las 4 camaras de 03_seed.sql como si
---- las 4 fueran simuladas/falsas. Mal: "Cam-Ingreso-01" es la webcam USB
---- REAL de la PC (indice 0) - se usa de verdad para deteccion de gesto
---- (modo panico) y sabotaje, no apunta a una IP inventada como las otras
---- 3. Esto la vuelve a activar; Patio/Estacionamiento/Pasillo (con IPs
---- de ejemplo que no existen) quedan Inactivas como corresponde.
----
----   sqlcmd -S localhost -E -C -i db/09_reactivar_webcam_pc.sql
----------------------------------------------------------------

USE bd_cam_seguridad;
GO

UPDATE cam.Camaras SET Estado = N'Activa'
WHERE Nombre = N'Cam-Ingreso-01' AND TipoConexion = N'USB';
GO

SELECT z.Nombre AS Zona, c.Nombre AS Camara, c.TipoConexion, c.UrlConexion, c.Estado
FROM cam.Camaras c JOIN cam.Zonas z ON z.IdZona = c.IdZona
ORDER BY c.IdCamara;
GO
