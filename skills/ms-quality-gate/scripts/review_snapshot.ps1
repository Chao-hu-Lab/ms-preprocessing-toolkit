param(
    [string]$Root = "."
)

$ErrorActionPreference = "Stop"
Set-Location $Root

Write-Host "== Git Status =="
git status --short

Write-Host ""
Write-Host "== Python Entry/Config Files =="
if (Test-Path "pyproject.toml") { Write-Host "pyproject.toml" }
if (Test-Path "main.py") { Write-Host "main.py" }
if (Test-Path "src") {
    Get-ChildItem -Path "src" -Recurse -Filter "*.py" |
        ForEach-Object { $_.FullName.Replace((Get-Location).Path + "\", "") } |
        Out-Host
}

Write-Host ""
Write-Host "== Risk Signals (TODO/FIXME/pass/broad except) =="
if (Get-Command rg -ErrorAction SilentlyContinue) {
    rg -n "TODO|FIXME|except Exception|^\s*pass\s*$" src tests -S
} else {
    Write-Host "rg not found; skip signal scan"
}

Write-Host ""
Write-Host "== Test Files =="
if (Test-Path tests) {
    Get-ChildItem tests -Filter "test_*.py" | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
} else {
    Write-Host "tests/ not found"
}
