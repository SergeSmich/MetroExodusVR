param(
    [string]$Dll = 'F:\Projects\MetroExodusVR\work\tmp-style1.dll',
    [string]$Tag = 'bindmenu',
    [int]$Wait = 120,
    [string]$Slot = '8',
    [string]$Source = '0xc'
)
$ErrorActionPreference = 'Stop'
$root = 'F:\SteamLibrary\steamapps\common\Metro Exodus'
$ver  = Join-Path $root 'versions\0.9.1'
$work = 'F:\Projects\MetroExodusVR\work'

Stop-Process -Name MetroExodus -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Copy-Item $Dll (Join-Path $ver 'MetroExodusVR.dll') -Force
Write-Output ("installed {0} {1}" -f (Split-Path $Dll -Leaf), (Get-FileHash $Dll -Algorithm SHA256).Hash.Substring(0,16))

# keep Fonts.slot = Fonts.source alive from the very first moment of the
# process, so the UI is built with the alias in place
$bindLog = Join-Path $work ("bind_{0}.log" -f $Tag)
$binder = Start-Process -FilePath 'python' `
    -ArgumentList @((Join-Path $work 'live_bind_font.py'), '--slot', $Slot, '--source', $Source,
                    '--wait', '240', '--seconds', [string]($Wait + 30)) `
    -RedirectStandardOutput $bindLog -RedirectStandardError ($bindLog + '.err') `
    -NoNewWindow -PassThru

$p = Start-Process -FilePath (Join-Path $ver 'MetroExodusVR-launcher.exe') -WorkingDirectory $ver -PassThru
Start-Sleep -Seconds $Wait

Write-Output '--- binder ---'
Get-Content $bindLog -ErrorAction SilentlyContinue | Select-Object -First 6
Get-Content ($bindLog + '.err') -ErrorAction SilentlyContinue | Select-Object -Last 6

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
    Get-Content $latest.FullName -Tail 6
}
