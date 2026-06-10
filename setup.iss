; Inno Setup script for 命运 (DESTINY) - 智能客户开发系统
; Brand: 曙光黄 #FBBF24 + 深色主题

#define MyAppName "命运 (DESTINY)"
#define MyAppNameShort "Destiny"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "Fortune SCM"
#define MyAppURL "https://fortune-scm.com"
#define MyAppExeName "Destiny.exe"

[Setup]
AppId={{DESTINY-SCM-2024}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppNameShort}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer-output
OutputBaseFilename=Destiny-Setup
SetupIconFile=frontend\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Dark theme colors
WizardImageAlphaFormat=defined
DisableWelcomePage=no
LicenseBackgroundColor=$0a0a0a
WizardSizePercent=100

; Brand colors via CLSID
; 曙光黄 accent on dark background

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Destiny\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Custom dark theme colors for wizard pages
procedure InitializeWizard();
begin
  // Set dark background for all wizard pages
  WizardForm.Color := $0a0a0a;  // Deep black
  WizardForm.Font.Color := $ededed;  // Light text

  // Welcome page
  if Assigned(WizardForm.WelcomeLabel1) then
  begin
    WizardForm.WelcomeLabel1.Font.Color := $24bbfa;  // 曙光黄 BGR
    WizardForm.WelcomeLabel1.Font.Size := 14;
    WizardForm.WelcomeLabel2.Font.Color := $a1a1a1;
  end;

  // Finished page
  if Assigned(WizardForm.FinishedLabel) then
  begin
    WizardForm.FinishedLabel.Font.Color := $a1a1a1;
  end;
end;

// Apply dark theme to all labels on each page
procedure CurPageChanged(CurPageID: Integer);
var
  i: Integer;
begin
  for i := 0 to WizardForm.ControlCount - 1 do
  begin
    if WizardForm.Controls[i] is TLabel then
    begin
      if (TLabel(WizardForm.Controls[i]).Font.Color <> $24bbfa) and
         (TLabel(WizardForm.Controls[i]).Font.Color <> clWhite) and
         (TLabel(WizardForm.Controls[i]).Font.Color <> $0a0a0a) then
        TLabel(WizardForm.Controls[i]).Font.Color := $a1a1a1;
    end;
  end;
end;
