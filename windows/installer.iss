; 眼動鼠 — Windows 安裝程式（Inno Setup 6）
#ifndef AppVer
  #define AppVer "1.0.0"
#endif
#define AppName "眼動鼠"
#define AppExe "EyeMouse.exe"

[Setup]
AppId={{B5E2A7C1-3D4F-4E8A-9C61-7F2E0A9D4B53}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=吳玉柱
AppPublisherURL=https://github.com/achir1015/eyemouse
DefaultDirName={autopf}\EyeMouse
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
OutputDir=..\dist-installer
OutputBaseFilename=EyeMouse-Setup
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
CloseApplications=force
RestartApplications=no

[Languages]
Name: "cht"; MessagesFile: "ChineseTraditional.isl"

[LangOptions]
DialogFontName=Microsoft JhengHei UI
DialogFontSize=14
WelcomeFontName=Microsoft JhengHei UI
WelcomeFontSize=20

[Tasks]
Name: "desktopicon"; Description: "在桌面建立捷徑"; GroupDescription: "其他："
Name: "autostart"; Description: "開機時自動啟動眼動鼠（臥床使用者建議勾選）"; GroupDescription: "其他："

[Files]
Source: "..\dist\EyeMouse\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "EyeMouse"; ValueData: """{app}\{#AppExe}"" --hidden"; Flags: uninsdeletevalue; Tasks: autostart

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autoprograms}\解除安裝 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "立即啟動 {#AppName}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: ShouldRelaunch

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "KillEyeMouse"

[Code]
function ShouldRelaunch(): Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;
