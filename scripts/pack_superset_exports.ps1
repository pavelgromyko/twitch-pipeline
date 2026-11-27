# Builds importable zip files from superset/exports/<dashboard>/ into superset/dist/
$out = "superset\dist"
New-Item -ItemType Directory -Force $out | Out-Null
Get-ChildItem superset\exports -Directory | ForEach-Object {
    tar -a -c -f "$out\$($_.Name).zip" -C superset\exports $_.Name
    "created $out\$($_.Name).zip"
}