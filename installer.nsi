Unicode true
!include "MUI2.nsh"
Name "Talevoxa"
OutFile "dist\QuietPages-Setup-Windows-x64.exe"
InstallDir "$LOCALAPPDATA\Programs\QuietPages"
RequestExecutionLevel user
SetCompressor /SOLID lzma
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "COPYING"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Talevoxa"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "dist\QuietPages\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Talevoxa"
  CreateShortcut "$SMPROGRAMS\Talevoxa\Talevoxa.lnk" "$INSTDIR\QuietPages.exe"
  CreateShortcut "$SMPROGRAMS\Talevoxa\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\QuietPages" "DisplayName" "Talevoxa"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\QuietPages" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\QuietPages" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\QuietPages" "DisplayIcon" "$INSTDIR\QuietPages.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\QuietPages" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\QuietPages" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  ; Remove only shipped paths. User books and LocalAppData\QuietPages are preserved.
  Delete "$INSTDIR\QuietPages.exe"
  Delete "$INSTDIR\Uninstall.exe"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\THIRD_PARTY.md"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\COPYING"
  Delete "$INSTDIR\VALIDATION.md"
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\licenses"
  RMDir /r "$INSTDIR\source"
  RMDir /r "$INSTDIR\third-party-source"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\Talevoxa\Talevoxa.lnk"
  Delete "$SMPROGRAMS\Talevoxa\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Talevoxa"
  Delete "$SMPROGRAMS\Quiet Pages\Quiet Pages.lnk"
  Delete "$SMPROGRAMS\Quiet Pages\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Quiet Pages"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\QuietPages"
SectionEnd
