param(
    [string]$Dll = 'F:\Projects\MetroExodusVR\work\tmp-utf8.dll',
    [string]$Tag = 'utf8',
    [int]$Wait = 150,
    [switch]$Navigate
)
$ErrorActionPreference = 'Stop'
$root = 'F:\SteamLibrary\steamapps\common\Metro Exodus'
$ver  = Join-Path $root 'versions\0.9.1'
$work = 'F:\Projects\MetroExodusVR\work'

Stop-Process -Name MetroExodus -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Copy-Item $Dll (Join-Path $ver 'MetroExodusVR.dll') -Force
Write-Output ("installed {0} {1}" -f (Split-Path $Dll -Leaf), (Get-FileHash $Dll -Algorithm SHA256).Hash.Substring(0,16))

$p = Start-Process -FilePath (Join-Path $ver 'MetroExodusVR-launcher.exe') -WorkingDirectory $ver -PassThru
Start-Sleep -Seconds $Wait

if (-not (Get-Process -Name MetroExodus -ErrorAction SilentlyContinue)) {
    Write-Output 'GAME NOT RUNNING'
} else {
    Write-Output 'game alive'
    & python (Join-Path $work 'nav.py') shot $Tag
}

$logdir = Join-Path $ver 'logs'
$latest = Get-ChildItem $logdir -File -Filter '*_hook_*.log' | Sort-Object LastWriteTime | Select-Object -Last 1
if ($latest) {
    Write-Output ("log {0} {1} B" -f $latest.Name, $latest.Length)
    Select-String -Path $latest.FullName -Pattern 'menus loaded|captions set' |
        Select-Object -Last 4 | ForEach-Object { $_.Line }
}
