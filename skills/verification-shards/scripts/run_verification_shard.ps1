param(
    [ValidateSet("smoke", "adapter", "gui", "integration", "perf", "markers", "collect", "full", "ms-core")]
    [string]$Shard = "smoke"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Set-Location $repoRoot

$msCoreSrc = Join-Path $repoRoot "ms-core\src"
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$msCoreSrc;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $msCoreSrc
}

switch ($Shard) {
    "smoke" {
        python -m pytest -m smoke -v --tb=short
        exit $LASTEXITCODE
    }
    "adapter" {
        python -m pytest -m adapter -v --tb=short
        exit $LASTEXITCODE
    }
    "gui" {
        python -m pytest -m gui -v --tb=short
        exit $LASTEXITCODE
    }
    "integration" {
        python -m pytest -m integration -v --tb=short
        exit $LASTEXITCODE
    }
    "perf" {
        python -m pytest -m perf -v --tb=short
        exit $LASTEXITCODE
    }
    "markers" {
        python -m pytest tests/test_testing_markers.py -v --tb=short
        exit $LASTEXITCODE
    }
    "collect" {
        python -m pytest --collect-only tests -q
        exit $LASTEXITCODE
    }
    "full" {
        python -m pytest tests/ -v --tb=short -x
        exit $LASTEXITCODE
    }
    "ms-core" {
        Push-Location ms-core
        try {
            python -m pytest tests/ -v --tb=short -x
            exit $LASTEXITCODE
        } finally {
            Pop-Location
        }
    }
}
