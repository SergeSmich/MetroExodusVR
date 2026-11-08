param(
    [Parameter(Mandatory=$true)][string[]]$Paths,
    [string]$Needle = 'Настройки',
    [int]$MaxMB = 2048
)

$encUtf8 = [System.Text.Encoding]::UTF8
$encU16 = [System.Text.Encoding]::Unicode

# byte patterns
function Get-Bytes([System.Text.Encoding]$enc, [string]$s) { $enc.GetBytes($s) }

$patterns = @{
    'UTF-8'   = (Get-Bytes $encUtf8 $Needle)
    'UTF-16LE'= (Get-Bytes $encU16 $Needle)
    'CP1251'  = ([System.Text.Encoding]::GetEncoding(1251).GetBytes($Needle))
}

foreach ($path in $Paths) {
    if (-not (Test-Path $path)) { "MISSING: $path"; continue }
    $fs = [System.IO.File]::OpenRead($path)
    try {
        $chunk = 1MB
        $buf = New-Object byte[] ($chunk + 32)
        $total = 0
        $hits = @{}
        foreach ($k in $patterns.Keys) { $hits[$k] = 0 }
        $read = 0
        while (($read = $fs.Read($buf, 0, $chunk)) -gt 0) {
            $total += $read
            foreach ($k in $patterns.Keys) {
                $pat = $patterns[$k]
                $span = New-Object byte[] ($read + $pat.Length - 1)
                [Array]::Copy($buf, 0, $span, 0, $read)
                # simple byte search
                $limit = $read
                for ($i = 0; $i -lt $limit; $i++) {
                    if ($span[$i] -eq $pat[0]) {
                        $ok = $true
                        for ($j = 1; $j -lt $pat.Length; $j++) {
                            if ($span[$i + $j] -ne $pat[$j]) { $ok = $false; break }
                        }
                        if ($ok) { $hits[$k]++; $i += $pat.Length - 1 }
                    }
                }
            }
            if ($total -ge ($MaxMB * 1MB)) { break }
        }
        # report
        $summary = ($hits.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ' '
        "SCANNED $([math]::Round($total/1MB,1)) MB: $path -> $summary"
    } finally { $fs.Close() }
}
