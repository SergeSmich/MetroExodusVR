param(
    [Parameter(Mandatory = $true)]
    [string]$OriginalDll,
    [switch]$BuildCandidate
)

$ErrorActionPreference = 'Stop'
$Expected = 'FBBF2812BC7C3304A22829249ABA334C812A326BAF75FC5C2A75E559202C40B4'
$Root = $PSScriptRoot

if (-not (Test-Path -LiteralPath $OriginalDll -PathType Leaf)) {
    throw "Original DLL not found: $OriginalDll"
}
$Actual = (Get-FileHash -LiteralPath $OriginalDll -Algorithm SHA256).Hash
if ($Actual -ne $Expected) {
    throw "Unsupported DLL SHA-256: $Actual (expected $Expected). No output was built."
}
Write-Host "Source SHA-256 verified: $Actual"

Push-Location $Root
try {
    & py .\tools\validate_ui2.py --dll $OriginalDll
    if ($LASTEXITCODE -ne 0) { throw 'Static catalog validation failed.' }

    & py .\tools\apply_ru.py --src $OriginalDll --check --no-fonts --experimental-cp1251
    if ($LASTEXITCODE -ne 0) { throw 'Patcher structural check failed.' }

    if (-not $BuildCandidate) {
        Write-Host 'No DLL was written. Pass -BuildCandidate only for an isolated runtime diagnostic.'
        return
    }

    Write-Warning 'This builds an experimental CP1251 diagnostic DLL; existing notes report bad rendering. It is not a release rusifier.'
    & py .\tools\merge_cyrillic.py --src $OriginalDll --out .\build\fonts
    if ($LASTEXITCODE -ne 0) { throw 'Font preparation failed.' }

    $Candidate = Join-Path $Root 'build\MetroExodusVR-RU-CP1251-DIAGNOSTIC.dll'
    if (Test-Path -LiteralPath $Candidate) {
        throw "Candidate already exists; move/delete it deliberately before rebuilding: $Candidate"
    }
    & py .\tools\apply_ru.py --src $OriginalDll --out $Candidate --verify --experimental-cp1251
    if ($LASTEXITCODE -ne 0) { throw 'Candidate build/verification failed.' }

    $CandidateHash = (Get-FileHash -LiteralPath $Candidate -Algorithm SHA256).Hash
    Write-Host "Diagnostic candidate: $Candidate"
    Write-Host "Candidate SHA-256:    $CandidateHash"
    Write-Warning 'The candidate has NOT been installed. Test only in an isolated mod copy or after making and verifying a backup.'
}
finally {
    Pop-Location
}
