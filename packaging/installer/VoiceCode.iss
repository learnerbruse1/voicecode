; Inno Setup installer script for VoiceCode.
; Build manually with Inno Setup 6:
;   ISCC.exe packaging\installer\VoiceCode.iss
; Or run packaging\installer\build-installer.ps1 from the repository root.

#define MyAppName "VoiceCode"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "VoiceCode contributors"
#ifndef SourceDir
#define SourceDir "dist\VoiceCode"
#endif

[Setup]
AppId={{A4B174E8-3C47-4AE2-A4BA-5605764593D4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=no
DisableProgramGroupPage=auto
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=VoiceCodeSetup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\..\LICENSE
UninstallDisplayIcon={app}\VoiceCode.exe
CloseApplications=yes
CloseApplicationsFilter=VoiceCode.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Dirs]
; The app defaults to a per-user install path. These writable runtime directories keep
; future Hugging Face / faster-whisper downloads under the chosen install directory.
Name: "{app}\runtime"; Permissions: users-modify
Name: "{app}\runtime\cache"; Permissions: users-modify
Name: "{app}\runtime\models"; Permissions: users-modify

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\VoiceCode.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\VoiceCode.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\VoiceCode.exe"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
