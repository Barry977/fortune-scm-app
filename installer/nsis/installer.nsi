; ═══════════════════════════════════════════════════════════
; 命运 (DESTINY) - NSIS 安装脚本
; 功能：安装向导、桌面快捷方式、开始菜单、卸载程序
; ═══════════════════════════════════════════════════════════

!include "MUI2.nsh"
!include "FileFunc.nsh"

; ── 基本信息 ──────────────────────────────────────────────
Name "命运 (DESTINY)"
OutFile "Destiny-Setup.exe"
InstallDir "$LOCALAPPDATA\Destiny"
InstallDirRegKey HKCU "Software\Destiny" "InstallDir"
RequestExecutionLevel user
Unicode True

; ── 版本信息 ──────────────────────────────────────────────
VIProductVersion "1.6.1.0"
VIAddVersionKey "ProductName" "命运 DESTINY"
VIAddVersionKey "FileVersion" "1.6.1"
VIAddVersionKey "FileDescription" "命运 (DESTINY) - LinkedIn 客户开发平台"
VIAddVersionKey "CompanyName" "Destiny"

; ── 界面设置 ──────────────────────────────────────────────
!define MUI_ABORTWARNING
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"

; ── 安装页面 ──────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "license.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; ── 卸载页面 ──────────────────────────────────────────────
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ── 语言 ──────────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ── 安装区段 ──────────────────────────────────────────────

Section "命运 (DESTINY) 主程序" SecMain
    SectionIn RO  ; 必选
    
    ; 设置安装目录
    SetOutPath "$INSTDIR"
    
    ; 复制所有文件（从 PyInstaller 输出目录）
    File /r "app\*.*"
    
    ; 写入注册表（卸载信息）
    WriteRegStr HKCU "Software\Destiny" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Destiny" \
        "DisplayName" "命运 (DESTINY)"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Destiny" \
        "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Destiny" \
        "DisplayIcon" '"$INSTDIR\Destiny.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Destiny" \
        "Publisher" "Destiny"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Destiny" \
        "DisplayVersion" "1.6.1"
    
    ; 计算安装大小
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Destiny" \
        "EstimatedSize" "$0"
    
    ; 创建卸载程序
    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "桌面快捷方式" SecDesktop
    CreateShortcut "$DESKTOP\命运 DESTINY.lnk" "$INSTDIR\Destiny.exe" "" "$INSTDIR\Destiny.exe" 0
SectionEnd

Section "开始菜单快捷方式" SecStartMenu
    CreateDirectory "$SMPROGRAMS\命运 DESTINY"
    CreateShortcut "$SMPROGRAMS\命运 DESTINY\命运 DESTINY.lnk" "$INSTDIR\Destiny.exe" "" "$INSTDIR\Destiny.exe" 0
    CreateShortcut "$SMPROGRAMS\命运 DESTINY\卸载.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0
SectionEnd

Section "开机自动启动" SecAutoStart
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Destiny" '"$INSTDIR\Destiny.exe" --minimized'
SectionEnd

; ── 区段描述 ──────────────────────────────────────────────
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "安装命运 (DESTINY) 主程序文件（必需）"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "在桌面创建快捷方式"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "在开始菜单创建程序组"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecAutoStart} "开机时自动启动命运（最小化到系统托盘）"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ── 安装回调 ──────────────────────────────────────────────
Function .onInit
    ; 检查是否已安装
    ReadRegStr $0 HKCU "Software\Destiny" "InstallDir"
    ${If} $0 != ""
        MessageBox MB_YESNO|MB_ICONQUESTION "检测到已安装命运 (DESTINY)。$\n$\n是否覆盖安装？" IDYES continue
        Abort
        continue:
    ${EndIf}
FunctionEnd

; ── 卸载区段 ──────────────────────────────────────────────
Section "Uninstall"
    ; 删除程序文件
    RMDir /r "$INSTDIR"
    
    ; 删除快捷方式
    Delete "$DESKTOP\命运 DESTINY.lnk"
    RMDir /r "$SMPROGRAMS\命运 DESTINY"
    
    ; 删除注册表
    DeleteRegKey HKCU "Software\Destiny"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Destiny"
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Destiny"
SectionEnd
