#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#ifndef BundleDir
  #define BundleDir "..\..\dist\portable-local-ai"
#endif
#ifndef AppVersionNumeric
  #define AppVersionNumeric "0.0.0.0"
#endif

[Setup]
AppId={{C84D3853-F139-4AA6-A069-AC41825E5D5C}
AppName=Portable Local AI
AppVersion={#AppVersion}
AppPublisher=Portable Local AI
DefaultDirName={localappdata}\Programs\Portable Local AI
DefaultGroupName=Portable Local AI
DisableProgramGroupPage=yes
DisableReadyMemo=no
DisableWelcomePage=no
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\release
OutputBaseFilename=Portable-Local-AI-Windows-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
UninstallDisplayName=Portable Local AI
VersionInfoVersion={#AppVersionNumeric}
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install-runtime.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion

[Dirs]
Name: "{localappdata}\PortableLocalAI"; Permissions: users-full
Name: "{userdocs}\Portable Local AI\Models"; Permissions: users-full

[Icons]
Name: "{group}\Portable Local AI"; Filename: "{app}\portable-local-ai.exe"
Name: "{group}\Local model folder"; Filename: "{userdocs}\Portable Local AI\Models"
Name: "{autodesktop}\Portable Local AI"; Filename: "{app}\portable-local-ai.exe"

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{app}\installer\install-runtime.ps1"" -AppDirectory ""{app}"" -AppExecutable ""{app}\portable-local-ai.exe"""; StatusMsg: "Detecting hardware and preparing the local AI runtime..."; Flags: runhidden waituntilterminated
Filename: "{app}\portable-local-ai.exe"; Description: "Open Portable Local AI"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoLogo -NoProfile -NonInteractive -Command ""Unregister-ScheduledTask -TaskPath '\Portable Local AI\' -TaskName 'Start Portable Local AI' -Confirm:$false -ErrorAction SilentlyContinue"""; Flags: runhidden waituntilterminated

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectDir then
    WizardForm.SelectDirLabel.Caption := 'Choose where the application files will be installed. Your models, conversations, and credentials are stored separately and preserved during upgrades.';
  if CurPageID = wpInstalling then
    WizardForm.StatusLabel.Caption := 'Installing the application and all required components...';
end;
