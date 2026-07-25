; Build with packaging/windows/build_windows_installer.py. Do not invoke directly.
#ifndef SourceDir
  #error SourceDir must point to the PyInstaller onedir output.
#endif
#ifndef OutputDir
  #error OutputDir must point to the installer output directory.
#endif
#ifndef AppVersion
  #error AppVersion must be supplied by the build script.
#endif
#ifndef IconFile
  #error IconFile must point to the VoiceCode ICO asset.
#endif

#define AppName "VoiceCode"
#define AppExeName "VoiceCode.exe"

[Setup]
AppId={{D1C4B621-7920-4AB7-9F21-20CC3A4A7D10}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher=VoiceCode contributors
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=VoiceCode-v{#AppVersion}-Windows-x64-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; The default is per-user and writable. This keeps future models and optional packages in
; {app}\runtime even when the user chooses a custom installation directory.
Name: "{app}\runtime"; Permissions: users-modify
Name: "{app}\runtime\dependencies"; Permissions: users-modify
Name: "{app}\runtime\models"; Permissions: users-modify
Name: "{app}\runtime\cache"; Permissions: users-modify

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; AppUserModelID: "VoiceCode.Desktop.0.2"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "VoiceCode.Desktop.0.2"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent; Check: not WizardSilent
