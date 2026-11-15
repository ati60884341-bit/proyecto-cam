----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 13_tipo_simulacro.sql : agrega "Simulacro" a los tipos de incidencia
----
---- Lo usa el boton de simulacion de incidente de la app Android (demo):
---- sin esto, el INSERT con Tipo='Simulacro' choca contra el CHECK viejo.
---- No borra nada. Ejecutar una vez:
----   sqlcmd -S localhost -E -C -i db/13_tipo_simulacro.sql
----------------------------------------------------------------

USE bd_cam_seguridad;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.check_constraints cc
    JOIN sys.columns col ON col.object_id = cc.parent_object_id AND col.column_id = cc.parent_column_id
    WHERE cc.parent_object_id = OBJECT_ID(N'cam.Incidencias')
      AND col.name = N'Tipo'
      AND cc.definition LIKE N'%Simulacro%'
)
BEGIN
    DECLARE @nombre_restriccion NVARCHAR(128) = (
        SELECT cc.name
        FROM sys.check_constraints cc
        JOIN sys.columns col ON col.object_id = cc.parent_object_id AND col.column_id = cc.parent_column_id
        WHERE cc.parent_object_id = OBJECT_ID(N'cam.Incidencias') AND col.name = N'Tipo'
    );
    IF @nombre_restriccion IS NOT NULL
    BEGIN
        -- EXEC(...) solo acepta variables/literales concatenados con '+', no
        -- una llamada a funcion como QUOTENAME(...) inline, hay que asignarla
        -- a una variable primero
        DECLARE @nombre_restriccion_entrecomillado NVARCHAR(150) = QUOTENAME(@nombre_restriccion);
        EXEC(N'ALTER TABLE cam.Incidencias DROP CONSTRAINT ' + @nombre_restriccion_entrecomillado);
    END
    ALTER TABLE cam.Incidencias ADD CONSTRAINT CK_Incidencias_Tipo
        CHECK (Tipo IN (N'Sabotaje', N'Panico', N'Fatiga', N'Manual', N'ComandoVoz', N'Simulacro'));
END
GO
