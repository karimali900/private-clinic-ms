; Inno Setup Script — Obstetrics Management System Installer
; Created by Karim Abdelaziz — 00201029927276
; To compile: right-click and "Compile" with Inno Setup, or:
;   iscc OMS_installer.iss

#define MyAppName "Obstetrics Management System"
#define MyAppShortName "OMS"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Karim Abdelaziz"
#define MyAppURL ""
#define MyAppExeName "OMS.exe"
#define MyAppAssocName "OMS Database"
#define MyAppAssocExt ".db"

[Setup]
; Basic
AppId={{B8F7A3D2-1C4E-4A5B-9D0F-6E2C8A7B3D1F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Destination
DefaultDirName={autopf}\{#MyAppShortName}
DefaultGroupName={#MyAppShortName}
DisableProgramGroupPage=yes
AllowNoIcons=yes

; Output
OutputDir=installer
OutputBaseFilename=OMS_Setup_v{#MyAppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra
SolidCompression=yes
LZMAUseSeparateProcess=yes
DiskSpanning=no

; Permissions
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Visual
WizardStyle=modern
WizardSmallImageFile=icon.bmp
WizardImageFile=side.bmp

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\start.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppShortName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppShortName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autoprograms}\{#MyAppShortName} (Data Folder)"; Filename: "{app}\data"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent shellexec

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /f /im {#MyAppExeName} 2>nul"; Flags: runhidden

[Registry]
; Associate .omsdb files (optional)
Root: HKA; Subkey: "Software\Classes\.omsdb\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppAssocName}"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocName}"; ValueType: string; ValueName: ""; ValueData: "{#MyAppAssocName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocName}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

; Firewall rule for port 5000
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules"; ValueType: string; ValueName: "OMS_Port_5000"; ValueData: "v2.30|Action=Allow|Active=TRUE|Dir=In|Protocol=6|Profile=Private|LPort=5000|App={app}\{#MyAppExeName}|Name=OMS Local Server (Port 5000)|Desc=Allow OMS to communicate on local network"; Flags: uninsdeletevalue

[Code]
procedure InitializeWizard();
begin
  WizardForm.LicenseMemo.Font.Color := clGreen;
  WizardForm.LicenseMemo.Font.Size := 9;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Ensure data directory is writable
  end;
end;

[CustomMessages]
english.LaunchAfterInstall=Launch Obstetrics Management System
arabic.LaunchAfterInstall=تشغيل نظام إدارة التوليد
