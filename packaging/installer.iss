; Inno Setup script: wraps dist\Jarvis into JarvisSetup.exe (installs per user, no admin needed).
; Build with: iscc packaging\installer.iss   (see packaging\build.ps1)

#define AppName "Jarvis"
#define AppVersion "0.1.0"

[Setup]
AppId={{6F1B2C0E-5D44-4C7A-9B0D-2A7E3C1D8F40}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=JarvisSetup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\Jarvis.exe
CloseApplications=yes

[Tasks]
Name: "startup"; Description: "Start Jarvis when I sign in to Windows"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Jarvis\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\.env.example"; DestDir: "{userappdata}\Jarvis"; DestName: ".env"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\Jarvis"; Filename: "{app}\Jarvis.exe"
Name: "{autodesktop}\Jarvis"; Filename: "{app}\Jarvis.exe"; Tasks: desktopicon
; The same Startup shortcut the tray's "Start with Windows" switch creates.
Name: "{userstartup}\Jarvis"; Filename: "{app}\Jarvis.exe"; Parameters: "--background"; Tasks: startup

[Run]
Filename: "{app}\Jarvis.exe"; Description: "Start Jarvis now"; Flags: nowait postinstall skipifsilent
