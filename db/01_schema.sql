----------------------------------------------------------------
---- PROYECTO CAM - Sistema Inteligente de Videovigilancia y Auditoria
---- 01_schema.sql : creacion de base de datos, esquema y tablas
----------------------------------------------------------------

IF DB_ID(N'bd_cam_seguridad') IS NOT NULL
BEGIN
    ALTER DATABASE bd_cam_seguridad SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE bd_cam_seguridad;
END
GO

CREATE DATABASE bd_cam_seguridad;
GO

USE bd_cam_seguridad;
GO

CREATE SCHEMA cam AUTHORIZATION dbo;
GO

----------------------------------------------------------------
---- Tabla: Usuarios (administradores y vigilantes del sistema)
----------------------------------------------------------------
CREATE TABLE cam.Usuarios (
    IdUsuario       INT IDENTITY(1,1) PRIMARY KEY,
    NombreCompleto  NVARCHAR(150) NOT NULL,
    NombreUsuario   NVARCHAR(50)  NOT NULL UNIQUE,
    ClaveHash       NVARCHAR(256) NOT NULL,   ---- SHA-256 de la contrasena ----
    Rol             NVARCHAR(20)  NOT NULL CHECK (Rol IN (N'Administrador', N'Vigilante')),
    Activo          BIT NOT NULL DEFAULT 1,
    FechaCreacion   DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

----------------------------------------------------------------
---- Tabla: Zonas (las 4 zonas fisicas de la maqueta)
----------------------------------------------------------------
CREATE TABLE cam.Zonas (
    IdZona      INT IDENTITY(1,1) PRIMARY KEY,
    Nombre      NVARCHAR(50) NOT NULL UNIQUE,
    Descripcion NVARCHAR(200) NULL
);
GO

----------------------------------------------------------------
---- Tabla: Camaras (adaptador universal multimarca)
----------------------------------------------------------------
CREATE TABLE cam.Camaras (
    IdCamara        INT IDENTITY(1,1) PRIMARY KEY,
    IdZona          INT NOT NULL REFERENCES cam.Zonas(IdZona),
    Nombre          NVARCHAR(100) NOT NULL,
    Marca           NVARCHAR(30)  NOT NULL CHECK (Marca IN (N'Hikvision', N'Dahua', N'Tapo', N'WebcamUSB', N'Generico')),
    TipoConexion    NVARCHAR(10)  NOT NULL CHECK (TipoConexion IN (N'RTSP', N'USB')),
    UrlConexion     NVARCHAR(300) NULL,       ---- url RTSP o indice de dispositivo USB ----
    Estado          NVARCHAR(20)  NOT NULL DEFAULT N'Activa' CHECK (Estado IN (N'Activa', N'Inactiva', N'Sabotaje')),
    FechaRegistro   DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

----------------------------------------------------------------
---- Tabla: Turnos (control de vigilantes en servicio)
----------------------------------------------------------------
CREATE TABLE cam.Turnos (
    IdTurno     INT IDENTITY(1,1) PRIMARY KEY,
    IdUsuario   INT NOT NULL REFERENCES cam.Usuarios(IdUsuario),
    FechaInicio DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    FechaFin    DATETIME2 NULL,
    Estado      NVARCHAR(20) NOT NULL DEFAULT N'Abierto' CHECK (Estado IN (N'Abierto', N'Cerrado'))
);
GO

----------------------------------------------------------------
---- Tabla: Incidencias (sabotajes, panico, fatiga, manuales)
----------------------------------------------------------------
CREATE TABLE cam.Incidencias (
    IdIncidencia  INT IDENTITY(1,1) PRIMARY KEY,
    IdZona        INT NOT NULL REFERENCES cam.Zonas(IdZona),
    IdCamara      INT NULL REFERENCES cam.Camaras(IdCamara),
    IdTurno       INT NULL REFERENCES cam.Turnos(IdTurno),
    Tipo          NVARCHAR(30) NOT NULL CHECK (Tipo IN (N'Sabotaje', N'Panico', N'Fatiga', N'Manual', N'ComandoVoz')),
    Severidad     NVARCHAR(20) NOT NULL DEFAULT N'Normal' CHECK (Severidad IN (N'Normal', N'Alta', N'Critica')),
    Descripcion   NVARCHAR(300) NULL,
    FechaHora     DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    Atendida      BIT NOT NULL DEFAULT 0,
    FechaAtencion DATETIME2 NULL
);
GO

----------------------------------------------------------------
---- Tabla: HistorialIncidencias (bitacora de cambios - trigger AFTER UPDATE)
----------------------------------------------------------------
CREATE TABLE cam.HistorialIncidencias (
    IdHistorial     INT IDENTITY(1,1) PRIMARY KEY,
    IdIncidencia    INT NOT NULL,
    AtendidaAnterior BIT,
    AtendidaNueva   BIT,
    SeveridadAnterior NVARCHAR(20),
    SeveridadNueva  NVARCHAR(20),
    FechaCambio     DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

----------------------------------------------------------------
---- Tabla: AlertasPanico (modo panico silencioso - bloquea borrado)
----------------------------------------------------------------
CREATE TABLE cam.AlertasPanico (
    IdAlerta        INT IDENTITY(1,1) PRIMARY KEY,
    IdIncidencia    INT NOT NULL REFERENCES cam.Incidencias(IdIncidencia),
    IdZona          INT NOT NULL REFERENCES cam.Zonas(IdZona),
    BloqueoBorrado  BIT NOT NULL DEFAULT 1,
    Atendida        BIT NOT NULL DEFAULT 0,
    FechaHora       DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

----------------------------------------------------------------
---- Tabla: Evidencias (fotos/videos firmados con SHA-256)
----------------------------------------------------------------
CREATE TABLE cam.Evidencias (
    IdEvidencia   INT IDENTITY(1,1) PRIMARY KEY,
    IdIncidencia  INT NULL REFERENCES cam.Incidencias(IdIncidencia),
    IdZona        INT NOT NULL REFERENCES cam.Zonas(IdZona),
    IdUsuario     INT NULL REFERENCES cam.Usuarios(IdUsuario),
    RutaArchivo   NVARCHAR(400) NOT NULL,
    TipoArchivo   NVARCHAR(10) NOT NULL CHECK (TipoArchivo IN (N'Foto', N'Video')),
    HashSHA256    CHAR(64) NOT NULL,
    FechaCaptura  DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

----------------------------------------------------------------
---- Tabla: EvidenciasEliminadas (respaldo historico - trigger INSTEAD OF DELETE)
----------------------------------------------------------------
CREATE TABLE cam.EvidenciasEliminadas (
    IdRegistro      INT IDENTITY(1,1) PRIMARY KEY,
    IdEvidencia     INT NOT NULL,
    RutaArchivo     NVARCHAR(400),
    HashSHA256      CHAR(64),
    IdUsuario       INT NULL,
    FechaEliminacion DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

----------------------------------------------------------------
---- Tabla: FatigaRegistros (auditor de fatiga / dead man's switch)
----------------------------------------------------------------
CREATE TABLE cam.FatigaRegistros (
    IdRegistro  INT IDENTITY(1,1) PRIMARY KEY,
    IdUsuario   INT NOT NULL REFERENCES cam.Usuarios(IdUsuario),
    IdTurno     INT NULL REFERENCES cam.Turnos(IdTurno),
    Confirmado  BIT NOT NULL,
    FechaHora   DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

----------------------------------------------------------------
---- Tabla: ComandosVoz (bitacora de comandos de voz ejecutados)
----------------------------------------------------------------
CREATE TABLE cam.ComandosVoz (
    IdComando   INT IDENTITY(1,1) PRIMARY KEY,
    IdUsuario   INT NULL REFERENCES cam.Usuarios(IdUsuario),
    Comando     NVARCHAR(200) NOT NULL,
    Resultado   NVARCHAR(200) NULL,
    FechaHora   DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

----------------------------------------------------------------
---- Tabla: HistorialTurnos (duracion de turnos cerrados - trigger AFTER UPDATE)
----------------------------------------------------------------
CREATE TABLE cam.HistorialTurnos (
    IdRegistro      INT IDENTITY(1,1) PRIMARY KEY,
    IdTurno         INT NOT NULL,
    IdUsuario       INT NOT NULL,
    DuracionMinutos INT NOT NULL,
    FechaCierre     DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO
