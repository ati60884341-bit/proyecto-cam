; Script de Inno Setup para empaquetar ProyectoCAM en un instalador .exe.
; Requiere tener Inno Setup instalado (gratis: https://jrsoftware.org/isdl.php)
; y haber corrido antes: venv\Scripts\pyinstaller.exe CAM.spec
; (debe existir la carpeta dist\ProyectoCAM antes de compilar este script).
;
; Compilar: abrir este archivo con el editor de Inno Setup y pulsar "Compile",
; o por linea de comandos: iscc installer.iss
; El instalador resultante queda en installer_output\ProyectoCAM_Setup.exe
;
; Prerrequisitos: el instalador YA INCLUYE e instala solos el Visual C++
; Redistributable x64 y el ODBC Driver 18 for SQL Server (son los .exe/.msi
; oficiales de Microsoft en prereqs\, bajados de sus paginas de descarga
; oficiales - no hace falta que la PC de destino los tenga de antemano).
; ProyectoCAM mismo se instala sin pedir administrador (PrivilegesRequired
; = lowest), pero esos dos instaladores de Microsoft SI piden sus propios
; permisos de administrador (Windows va a mostrar su UAC para esos dos
; pasos nada mas, no para el resto de la instalacion). Si alguna vez hay
; que renovarlos (hay una version mas nueva, o el link oficial cambio),
; se vuelven a bajar y se pisan los mismos dos archivos en prereqs\:
;   Visual C++ Redistributable x64: https://aka.ms/vs/17/release/vc_redist.x64.exe
;   ODBC Driver 18 for SQL Server (x64, ingles): revisar el link vigente en
;   https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server
;   (el fwlink viejo que estaba comentado aca quedo dado de baja)

#define MyAppName "ProyectoCAM"
#define MyAppVersion "1.0.0"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
; instala en una carpeta propia del usuario (no en Program Files) para que
; el .exe pueda escribir ahi sin pedir permisos de administrador
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename={#MyAppName}_Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Files]
; copia toda la carpeta generada por PyInstaller
Source: "dist\ProyectoCAM\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

; Prerrequisitos incluidos en el instalador (.exe/.msi oficiales de Microsoft,
; descargados en prereqs\ - ver comentario de [Run] para el porque de cada uno)
Source: "prereqs\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "prereqs\msodbcsql18.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Run]
; Visual C++ Redistributable x64 (lo necesitan opencv/mediapipe): se instala
; siempre que no corra en modo silencioso - el instalador oficial de
; Microsoft ya detecta solo si una version igual o mas nueva esta puesta y
; no hace nada en ese caso, asi que es seguro correrlo de todas formas.
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Instalando Visual C++ Redistributable..."; Flags: waituntilterminated
; ODBC Driver 18 for SQL Server (lo necesita pyodbc para hablar con SQL
; Server): mismo caso, el MSI reinstala/actualiza sin romper nada si ya
; estaba puesto.
Filename: "{sys}\msiexec.exe"; Parameters: "/i ""{tmp}\msodbcsql18.msi"" /quiet IACCEPTMSODBCSQLLICENSETERMS=YES"; StatusMsg: "Instalando ODBC Driver 18 for SQL Server..."; Flags: waituntilterminated
Filename: "{app}\ProyectoCAM.exe"; Description: "Ejecutar {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\ProyectoCAM.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\ProyectoCAM.exe"
