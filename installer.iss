; Script de Inno Setup para empaquetar ProyectoCAM en un instalador .exe.
; Requiere tener Inno Setup instalado (gratis: https://jrsoftware.org/isdl.php)
; y haber corrido antes: venv\Scripts\pyinstaller.exe CAM.spec
; (debe existir la carpeta dist\ProyectoCAM antes de compilar este script).
;
; Compilar: abrir este archivo con el editor de Inno Setup y pulsar "Compile",
; o por linea de comandos: iscc installer.iss
; El instalador resultante queda en installer_output\ProyectoCAM_Setup.exe

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

; -- Prerrequisitos opcionales (descargar los .exe oficiales y descomentar) --
; ODBC Driver 18 for SQL Server (lo necesita pyodbc para hablar con SQL Server):
;   https://go.microsoft.com/fwlink/?linkid=2278537 -> guardar como prereqs\msodbcsql18.msi
; Visual C++ Redistributable x64 (lo necesitan opencv/mediapipe):
;   https://aka.ms/vs/17/release/vc_redist.x64.exe -> guardar como prereqs\vc_redist.x64.exe
; Source: "prereqs\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
; Source: "prereqs\msodbcsql18.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Run]
; Source: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Instalando Visual C++ Redistributable..."
; Source: "msiexec.exe"; Parameters: "/i ""{tmp}\msodbcsql18.msi"" /quiet IACCEPTMSODBCSQLLICENSETERMS=YES"; StatusMsg: "Instalando ODBC Driver 18 for SQL Server..."
Filename: "{app}\ProyectoCAM.exe"; Description: "Ejecutar {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\ProyectoCAM.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\ProyectoCAM.exe"
