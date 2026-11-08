param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$Pattern,
    [int]$MinLen = 6,
    [int]$Limit = 100
)

$bytes = [System.IO.File]::ReadAllBytes($Path)
$text = [System.Text.Encoding]::ASCII.GetString($bytes)
$ms = [regex]::Matches($text, "[\x20-\x7E]{$MinLen,}")

$n = 0
foreach ($m in $ms) {
    $v = $m.Value
    if ($v -cmatch $Pattern) {
        $n++
        if ($n -le $Limit) { $v }
    }
}
"--- total matches: $n ---"
