# Destiny Installer - PowerShell script
# Creates a self-extracting installer with shortcuts

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Destiny"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName PresentationFramework

# ── Brand ──
$AppName = "命运 (DESTINY)"
$ExeName = "Destiny.exe"
$AppDir = Join-Path $PSScriptRoot "app"

# ── Welcome Dialog ──
$welcome = [System.Windows.Forms.MessageBox]::Show(
    "欢迎安装 命运 (DESTINY) 智能客户开发系统`n`n点击确定开始安装",
    "安装 $AppName",
    [System.Windows.Forms.MessageBoxButtons]::OKCancel,
    [System.Windows.Forms.MessageBoxIcon]::Information
)
if ($welcome -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }

# ── Copy Files ──
$progress = New-Object System.Windows.Forms.Form
$progress.Text = "安装中..."
$progress.Size = New-Object System.Drawing.Size(400, 120)
$progress.StartPosition = "CenterScreen"
$progress.FormBorderStyle = "FixedDialog"
$progress.MaximizeBox = $false

$label = New-Object System.Windows.Forms.Label
$label.Text = "正在安装 $AppName..."
$label.Location = New-Object System.Drawing.Point(20, 15)
$label.Size = New-Object System.Drawing.Size(350, 20)
$progress.Controls.Add($label)

$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Location = New-Object System.Drawing.Point(20, 45)
$bar.Size = New-Object System.Drawing.Size(350, 25)
$bar.Style = "Continuous"
$progress.Controls.Add($bar)

$progress.Show()
$progress.Refresh()

# Create install directory
$bar.Value = 10
$label.Text = "正在创建安装目录..."
$progress.Refresh()
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

# Copy files
$bar.Value = 30
$label.Text = "正在复制文件..."
$progress.Refresh()
Copy-Item -Path "$AppDir\*" -Destination $InstallDir -Recurse -Force

# Create desktop shortcut
$bar.Value = 70
$label.Text = "正在创建快捷方式..."
$progress.Refresh()
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "$AppName.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $InstallDir $ExeName
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = Join-Path $InstallDir $ExeName
$shortcut.Save()

# Create start menu entry
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$AppName"
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
$menuShortcut = Join-Path $startMenu "$AppName.lnk"
$ms = $shell.CreateShortcut($menuShortcut)
$ms.TargetPath = Join-Path $InstallDir $ExeName
$ms.WorkingDirectory = $InstallDir
$ms.IconLocation = Join-Path $InstallDir $ExeName
$ms.Save()

# Create uninstaller
$uninstallScript = @"
`$ErrorActionPreference = 'Stop'
`$desktopPath = [Environment]::GetFolderPath('Desktop')
Remove-Item (Join-Path `$desktopPath '$AppName.lnk') -Force -ErrorAction SilentlyContinue
Remove-Item '$startMenu' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item '$InstallDir' -Recurse -Force
"@
$uninstallPath = Join-Path $InstallDir "uninstall.ps1"
Set-Content -Path $uninstallPath -Value $uninstallScript

$bar.Value = 100
$label.Text = "安装完成！"
$progress.Refresh()
Start-Sleep -Milliseconds 500
$progress.Close()

# ── Done ──
$done = [System.Windows.Forms.MessageBox]::Show(
    "安装完成！`n`n安装位置: $InstallDir`n桌面快捷方式已创建`n`n是否立即运行？",
    "安装完成",
    [System.Windows.Forms.MessageBoxButtons]::YesNo,
    [System.Windows.Forms.MessageBoxIcon]::Information
)
if ($done -eq [System.Windows.Forms.DialogResult]::Yes) {
    Start-Process (Join-Path $InstallDir $ExeName) -WorkingDirectory $InstallDir
}
