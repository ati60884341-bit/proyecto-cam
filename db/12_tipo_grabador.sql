----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 12_tipo_grabador.sql : cada grabador dice si es DVR o NVR
----
---- El Centro de Monitoreo agrupa las camaras bajo "DVR ..." o "NVR ..."
---- segun esta columna. No borra nada (IF NOT EXISTS). Ejecutar una vez:
----   sqlcmd -S localhost -E -C -i db/12_tipo_grabador.sql
----------------------------------------------------------------

USE bd_cam_seguridad;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'cam.DispositivosDVR') AND name = N'Tipo')
BEGIN
    ALTER TABLE cam.DispositivosDVR ADD Tipo NVARCHAR(3) NOT NULL
        CONSTRAINT DF_DispositivosDVR_Tipo DEFAULT N'DVR'
        CONSTRAINT CK_DispositivosDVR_Tipo CHECK (Tipo IN (N'DVR', N'NVR'));
END
GO
