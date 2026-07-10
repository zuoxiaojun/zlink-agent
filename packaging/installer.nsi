; ===========================================================================
; ZLink Agent Windows NSIS Installer
;
; Usage: makensis packaging\installer.nsi
; Prerequisites: NSIS 3.0+ with Unicode support
; ===========================================================================

Unicode True
RequestExecutionLevel user

!define PRODUCT_NAME "ZLink Agent"
!define PRODUCT_VERSION "1.5.0"
!define PRODUCT_PUBLISHER "ZLink Agent"
!define PRODUCT_WEB_SITE "http://127.0.0.1:8089"
!define PRODUCT_DIR_REGKEY "Software\ZLink Agent"
!define PRODUCT_UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_STARTMENU_REGVAL "NSIS:StartMenuDir"

SetCompressor lzma

; ── Includes ─────────────────────────────────────────────────────────────
!include "MUI2.nsh"
!include "FileFunc.nsh"

; ── Interface ────────────────────────────────────────────────────────────
!define MUI_ABORTWARNING
!define MUI_ICON "packaging\app-icon.ico"
!define MUI_UNICON "packaging\app-icon.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP ""
!define MUI_WELCOMEFINISHPAGE_BITMAP ""

; ── Pages ────────────────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_STARTMENU Application $STARTMENU_FOLDER
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ── Languages ────────────────────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ── Installer info ───────────────────────────────────────────────────────
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "dist\ZLink-Agent-${PRODUCT_VERSION}-Setup.exe"
InstallDir "$LOCALAPPDATA\${PRODUCT_NAME}"
InstallDirRegKey HKCU "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show

; ── Sections ────────────────────────────────────────────────────────────
Section "Main" SEC_MAIN
  SetOutPath "$INSTDIR"
  SetOverwrite try

  ; Bundle PyInstaller output (dist/ZLink-Agent/)
  File /r "dist\ZLink-Agent\*.*"

  ; Write uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; Registry — uninstall info
  WriteRegStr HKCU "${PRODUCT_UNINSTALL_KEY}" "DisplayName" "${PRODUCT_NAME} ${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_UNINSTALL_KEY}" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKCU "${PRODUCT_UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\zlink-agent.exe"
  WriteRegStr HKCU "${PRODUCT_UNINSTALL_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_UNINSTALL_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKCU "${PRODUCT_UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegDWORD HKCU "${PRODUCT_UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${PRODUCT_UNINSTALL_KEY}" "NoRepair" 1

  ; Registry — install path
  WriteRegStr HKCU "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR"

  ; Start menu shortcuts
  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    CreateDirectory "$SMPROGRAMS\$STARTMENU_FOLDER"
    CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\ZLink Agent.lnk" "$INSTDIR\start-zlink-agent.bat" "" "$INSTDIR\zlink-agent.exe" 0
    CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\卸载 ZLink Agent.lnk" "$INSTDIR\uninstall.exe"
  !insertmacro MUI_STARTMENU_WRITE_END

  ; Desktop shortcut (optional)
  CreateShortCut "$DESKTOP\ZLink Agent.lnk" "$INSTDIR\start-zlink-agent.bat" "" "$INSTDIR\zlink-agent.exe" 0

  ; Estimate installed size
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "${PRODUCT_UNINSTALL_KEY}" "EstimatedSize" "$0"
SectionEnd

; ── Uninstaller ────────────────────────────────────────────────────────
Section "Uninstall"
  ; Remove installed files (except user data)
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\zlink-agent.exe"
  Delete "$INSTDIR\start-zlink-agent.bat"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"

  ; Remove shortcuts
  !insertmacro MUI_STARTMENU_GETFOLDER Application $STARTMENU_FOLDER
  RMDir /r "$SMPROGRAMS\$STARTMENU_FOLDER"
  Delete "$DESKTOP\ZLink Agent.lnk"

  ; Remove registry keys
  DeleteRegKey HKCU "${PRODUCT_UNINSTALL_KEY}"
  DeleteRegKey HKCU "${PRODUCT_DIR_REGKEY}"
SectionEnd