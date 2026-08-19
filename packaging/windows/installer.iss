#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#ifndef BundleDir
  #define BundleDir "..\..\dist\local-ai"
#endif
#ifndef AppVersionNumeric
  #define AppVersionNumeric "0.0.0.0"
#endif

[Setup]
AppId={{6F1B0A80-9F44-4C67-AB1C-785B2D2A31E4}
AppName=Local AI
AppVersion={#AppVersion}
AppPublisher=Local AI
DefaultDirName={autopf}\Local AI
DefaultGroupName=Local AI
DisableProgramGroupPage=yes
DisableReadyMemo=no
DisableWelcomePage=no
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\release
OutputBaseFilename=Local-AI-Windows-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
UninstallDisplayName=Local AI
VersionInfoVersion={#AppVersionNumeric}
CloseApplications=yes
RestartApplications=no
ChangesEnvironment=no

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install-runtime.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion

[Dirs]
Name: "{localappdata}\Local AI"
Name: "{localappdata}\Local AI\Models"
Name: "{localappdata}\Local AI\runtime\logs"

[Icons]
Name: "{group}\Local AI"; Filename: "{app}\local-ai.exe"
Name: "{group}\Local AI models"; Filename: "{localappdata}\Local AI\Models"
Name: "{autodesktop}\Local AI"; Filename: "{app}\local-ai.exe"

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{app}\installer\install-runtime.ps1"" -AppDirectory ""{app}"" -AppExecutable ""{app}\local-ai.exe"" -AppCliExecutable ""{app}\local-ai-cli.exe"""; StatusMsg: "Detecting hardware and preparing the Local AI runtime..."; Flags: runhidden waituntilterminated runasoriginaluser
Filename: "{app}\local-ai.exe"; Description: "Open Local AI"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoLogo -NoProfile -NonInteractive -Command ""Unregister-ScheduledTask -TaskPath '\Local AI\' -TaskName 'Start Local AI' -Confirm:$false -ErrorAction SilentlyContinue"""; Flags: runhidden waituntilterminated

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectDir then
    WizardForm.SelectDirLabel.Caption := 'Local AI is installed for this computer. Application files default to C:\Program Files\Local AI. Each user keeps private models, conversations, and credentials under their Windows profile; those files are preserved during upgrades and uninstall.';
  if CurPageID = wpInstalling then
    WizardForm.StatusLabel.Caption := 'Installing Local AI and all required components for this computer...';
end;
