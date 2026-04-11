$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$literalTargets = @(
    ".tmp",
    "build\pytest\tmp-fixtures",
    "build\pytest",
    ".pytest_cache",
    ".pytest-local-temp",
    ".pytest-tmp",
    "__pycache__"
)

foreach ($target in $literalTargets) {
    $path = Join-Path $root $target
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Get-ChildItem -Path $root -Force -Filter "tmp*" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
}
