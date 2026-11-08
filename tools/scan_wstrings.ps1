param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$Pattern,
    [int]$MinLen = 4,
    [int]$Limit = 200
)

$bytes = [System.IO.File]::ReadAllBytes($Path)
$text = [System.Text.Encoding]::Unicode.GetString($bytes)
$ms = [regex]::Matches($text, "[\x20-\x7E\u0400-\u04FF]{$MinLen,}")

$n = 0
foreach ($m in $ms) {
    $v = $m.Value
    if ($v -match $Pattern) {
        $n++
        if ($n -le $Limit) { $v }
    }
}
"--- total matches: $n ---"
