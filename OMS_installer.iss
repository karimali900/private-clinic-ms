; Inno Setup Script — Private Clinic OMS Installer
; Created by Karim Abdelaziz — 00201029927276
; Build with Inno Setup (https://jrsoftware.org/isinfo.php)

#define MyAppName "Private Clinic — Obstetrics Management"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Karim Abdelaziz"
#define MyAppURL "https://github.com/karimali900/private-clinic-ms"
#define MyAppExeName "OMS.exe"
#define MyAppAssocName "OMS Database"
#define MyAppAssocExt ".db"

[Setup]
AppId={{D8F2E3A1-5B7C-4A9E-8F6D-2C1B3A5E7F90}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\Private Clinic OMS
DefaultGroupName="Private Clinic OMS"
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=PrivateClinic_OMS_Setup_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
SetupIconFile=data\logos\default.jpg
UninstallDisplayIcon={app}\OMS.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\OMS.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "start.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\Private Clinic OMS\Data Folder"; Filename: "{app}\data"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /IM OMS.exe /F /T"; Flags: runhidden

[Code]
function InitializeSetup: Boolean;
begin
  if not FileExists(ExpandConstant('{src}\dist\OMS.exe')) then
  begin
    MsgBox('OMS.exe not found!' + #13#10 +
           'Please run build.bat first to compile the executable.', mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;
