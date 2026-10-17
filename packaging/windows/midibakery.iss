; MidiBakery's Windows setup (Inno Setup 6). Built by packaging/windows/build_setup.py, which passes:
;   /DVersion=<x.y.z>  /DAppSource=<the packaged app folder>  /DOutputDir=<where the setup goes>
;
; Installs for the current user, no administrator: the app into
; %LOCALAPPDATA%\Programs\MidiBakery\runtime\<version>\, then runs `midibakery install`, which puts the
; Remote Script and the devices into the User Library Live uses and keeps the API's settings of an
; earlier install. A newer setup updates in place; the uninstaller runs `midibakery uninstall` first.

#ifndef Version
  #error Pass /DVersion=<x.y.z>
#endif

[Setup]
; Never change the AppId: updates and the uninstaller find an install by it.
AppId={{B658F9AA-790E-478E-9CA7-C50CAB728F45}
AppName=MidiBakery
AppVersion={#Version}
AppVerName=MidiBakery {#Version}
AppPublisher=Klirrwerk
AppPublisherURL=https://klirrwerk.com
DefaultDirName={localappdata}\Programs\MidiBakery
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=MidiBakery-{#Version}-windows-x64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=MidiBakery
UninstallDisplayIcon={app}\runtime\{#Version}\midibakery.exe
; An API from this version that is still running holds its files: offer to close it.
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}\runtime\{#Version}"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallRun]
; Removes the Remote Script, the devices and launcher.json; settings and stored analyses stay.
Filename: "{app}\runtime\{#Version}\midibakery.exe"; Parameters: "uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "MidiBakeryUninstall"

[UninstallDelete]
; Older versions' runtime folders that `midibakery install` could not remove yet (their API was running).
Type: filesandordirs; Name: "{app}\runtime"
Type: files; Name: "{app}\install.log"

[Messages]
FinishedLabel=MidiBakery is installed.%n%nRestart Ableton Live. First time only: in Live's Settings > Link, Tempo & MIDI, choose MidiBakery as a Control Surface.%n%nEach device's About button shows the versions in use.

[Code]
function LiveIsRunning(): Boolean;
var
  Locator, Service, Processes: Variant;
begin
  Result := False;
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('.', 'root\CIMV2');
    Processes := Service.ExecQuery('SELECT ProcessId FROM Win32_Process WHERE Name LIKE ''Ableton Live%''');
    Result := Processes.Count > 0;
  except
    Result := False;
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if LiveIsRunning() then
    SuppressibleMsgBox('Ableton Live is running. You can install now: MidiBakery takes effect when you restart Live.',
      mbInformation, MB_OK, IDOK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  App, Log: String;
  ResultCode: Integer;
begin
  if CurStep <> ssPostInstall then
    Exit;
  App := ExpandConstant('{app}\runtime\{#Version}\midibakery.exe');
  Log := ExpandConstant('{app}\install.log');
  // cmd /C ""<app>" install >> "<log>" 2>&1": the output goes to the log, a failure is shown
  if not Exec(ExpandConstant('{cmd}'), '/C ""' + App + '" install >> "' + Log + '" 2>&1"', '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
    SuppressibleMsgBox('MidiBakery could not install its Remote Script and devices into Live (error '
      + IntToStr(ResultCode) + '). Details: ' + Log, mbError, MB_OK, IDOK);
end;
