; Inno Setup script — per-user install, no admin rights needed.
#define AppVersion GetEnv("DS_VERSION")
#if AppVersion == ""
  #define AppVersion "1.1.0"
#endif

[Setup]
AppId={{6C1E2B0A-7D5F-4E8B-9F3A-D7A5F1C2B3E4}
AppName=Tesler
AppVersion={#AppVersion}
AppPublisher=Tesler
DefaultDirName={localappdata}\Programs\Tesler
DefaultGroupName=Tesler
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Tesler-Setup
SetupIconFile=..\dragshift\assets\tesler.ico
UninstallDisplayIcon={app}\Tesler.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "autostart"; Description: "Start Tesler when I sign in to Windows"; Flags: checkedonce
Name: "contextmenu"; Description: "Add ""Tesler"" to the right-click menu for files"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Tesler\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Tesler"; Filename: "{app}\Tesler.exe"
Name: "{autodesktop}\Tesler"; Filename: "{app}\Tesler.exe"; Tasks: desktopicon
Name: "{usersendto}\Tesler"; Filename: "{app}\Tesler.exe"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Tesler"; ValueData: """{app}\Tesler.exe"" --quiet"; Tasks: autostart; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\*\shell\Tesler"; ValueType: string; ValueName: "MUIVerb"; ValueData: "Tesler…"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\Tesler"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\Tesler.exe"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\Tesler"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\Tesler\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Tesler.exe"" ""%1"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Tesler"; Flags: uninsdeletekey

[Run]
Filename: "{app}\Tesler.exe"; Description: "Launch Tesler now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM Tesler.exe"; Flags: runhidden; RunOnceId: "KillTesler"
