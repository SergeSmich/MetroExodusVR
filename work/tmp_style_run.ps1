param(
    [string]$Dll = 'F:\Projects\MetroExodusVR\work\tmp-style1.dll',
    [string]$Tag = 'style1',
    [int]$Wait = 120
)
$ErrorActionPreference = 'Stop'
$root = 'F:\SteamLibrary\steamapps\common\Metro Exodus'
$ver  = Join-Path $root 'versions\0.9.1'
$work = 'F:\Projects\MetroExodusVR\work'

Stop-Process -Name MetroExodus -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Copy-Item $Dll (Join-Path $ver 'MetroExodusVR.dll') -Force
Write-Output ("installed {0} {1}" -f (Split-Path $Dll -Leaf), (Get-FileHash $Dll -Algorithm SHA256).Hash.Substring(0,16))

# patcher first: it polls for MetroExodus.exe and patches the two lea
# displacements as soon as the image is mapped
$patchLog = Join-Path $work ("patch_{0}.log" -f $Tag)
$patcher = Start-Process -FilePath 'python' `
    -ArgumentList @((Join-Path $work 'patch_style_font.py'), '--timeout', '240') `
    -RedirectStandardOutput $patchLog -RedirectStandardError ($patchLog + '.err') `
    -NoNewWindow -PassThru

$p = Start-Process -FilePath (Join-Path $ver 'MetroExodusVR-launcher.exe') -WorkingDirectory $ver -PassThru
Start-Sleep -Seconds $Wait

if ($patcher -and -not $patcher.HasExited) {
    $patcher.WaitForExit(20000) | Out-Null
}
Write-Output '--- patcher ---'
Get-Content $patchLog -ErrorAction SilentlyContinue
Get-Content ($patchLog + '.err') -ErrorAction SilentlyContinue

if (-not (Get-Process -Name MetroExodus -ErrorAction SilentlyContinue)) {
    Write-Output 'GAME NOT RUNNING'
} else {
    Write-Output 'game alive'
    & python (Join-Path $work 'nav.py') shot $Tag
    & python (Join-Path $work 'patch_style_font.py') --verify-only 2>&1 | Select-Object -Last 8
}

$logdir = Join-Path $ver 'logs'
$latest = Get-ChildItem $logdir -File -Filter '*_hook_*.log' | Sort-Object LastWriteTime | Select-Object -Last 1
if ($latest) {
    Write-Output ("log {0} {1} B" -f $latest.Name, $latest.Length)
    Get-Content $latest.FullName -Tail 10
}
