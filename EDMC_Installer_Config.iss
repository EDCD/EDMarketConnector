#define MyAppName "EDMarketConnector"
#define MyAppVersion "5.9.1-alpha1"
#define MyAppPublisher "EDCD"
#define MyAppURL "https://edcd.github.io/"
#define SuppURL "https://github.com/EDCD/EDMarketConnector/"
#define MyAppExeName "EDMarketConnector.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{5B5AB12D-23A6-47BB-B937-07F23FF0BF86}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#SuppURL}
AppUpdatesURL={#SuppURL}
AppCopyright=Copyright (C) 2015-2019 Jonathan Harris, 2020-2023 EDCD
AllowUNCPath=no
AllowNetworkDrive=no
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DirExistsWarning=yes
AllowNoIcons=yes
; Uncomment the following line to run in non administrative install mode (install for current user only.)
;PrivilegesRequired=lowest
OutputBaseFilename=EDMarketConnector_Installer_{#MyAppVersion}
SetupIconFile=dist.win32\EDMarketConnector.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
InfoBeforeFile=dist.win32\Changelog.md
OutputDir=.
LicenseFile=LICENSE
LanguageDetectionMethod=uilanguage


[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist.win32\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist.win32\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
