; Hangazonosito installer (Inno Setup 6) - Vadóc Gábor, 2026
#define AppName "Hangazonosító"
#define AppVersion "1.0.0"
#define AppExe "Hangazonosito.exe"

[Setup]
AppId={{5D9A3E71-7B0C-4F36-9C1A-2E84B6D07A55}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Vadóc Gábor
AppPublisherURL=https://github.com/vadocgabi/hangazonosito
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UsedUserAreasWarning=no
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=app.ico
WizardStyle=modern
WizardImageFile=installer_side.bmp
WizardSmallImageFile=installer_small.bmp
DisableReadyPage=yes
OutputDir=installer
OutputBaseFilename=Hangazonosito-Setup-{#AppVersion}
Compression=lzma2/fast
SolidCompression=yes
VersionInfoVersion={#AppVersion}
VersionInfoCompany=Vadóc Gábor
VersionInfoDescription={#AppName} Setup
VersionInfoCopyright=© 2026 Vadóc Gábor

[Languages]
Name: "hungarian"; MessagesFile: "compiler:Languages\Hungarian.isl"; InfoBeforeFile: "info_hu.txt"
Name: "english"; MessagesFile: "compiler:Default.isl"; InfoBeforeFile: "info_en.txt"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[CustomMessages]
hungarian.CreateDesktopIcon=Parancsikon az asztalon
english.CreateDesktopIcon=Create a desktop shortcut

[Files]
Source: "dist\Hangazonosito\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
