param([string]$Path = ".")

if (-not (Test-Path ".env")) { Write-Output "ERROR: .env not found (run from project root)"; exit 2 }

$secrets = Get-Content .env | Where-Object { $_ -match '^[A-Za-z_]*(SECRET|PASSWORD|KEY|TOKEN)[A-Za-z_]*=(.{6,})$' } | ForEach-Object {
    $name, $value = $_ -split '=', 2
    [pscustomobject]@{ Name = $name; Value = $value }
}

$files = Get-ChildItem $Path -Recurse -File -Force | Where-Object {
    $_.FullName -notmatch '\\(\.git|\.venv|logs|data|__pycache__)\\' -and
    $_.Name -ne '.env' -and
    $_.Extension -notin '.png', '.jpg', '.jpeg', '.zip'
}

Write-Output "Secrets checked: $($secrets.Count), files scanned: $($files.Count)"
$found = 0
foreach ($s in $secrets) {
    $hits = $files | Select-String -SimpleMatch -Pattern $s.Value -List
    foreach ($h in $hits) {
        Write-Output "FOUND: $($s.Name) in $($h.Path)"
        $found++
    }
}
if ($found -eq 0) { Write-Output "OK: no secrets found" } else { Write-Output "STOP: $found match(es)" }