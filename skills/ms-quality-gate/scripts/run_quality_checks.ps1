param(
    [switch]$Fast,
    [switch]$SkipRuff,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
$results = @()
$failedRequired = $false

function Add-SkippedResult {
    param(
        [string]$Name,
        [string]$Reason
    )
    $script:results += [pscustomobject]@{
        Name = $Name
        Status = "skipped"
        ExitCode = $null
        Required = $false
        Output = $Reason
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action,
        [bool]$Required = $true
    )

    $exitCode = 0
    $output = ""
    try {
        $output = (& $Action 2>&1 | Out-String).Trim()
        if ($null -ne $LASTEXITCODE) {
            $exitCode = [int]$LASTEXITCODE
        }
    } catch {
        $exitCode = 1
        $output = ($_ | Out-String).Trim()
    }

    $ok = ($exitCode -eq 0)
    if (-not $ok -and $Required) {
        $script:failedRequired = $true
    }

    $script:results += [pscustomobject]@{
        Name = $Name
        Status = $(if ($ok) { "pass" } else { "fail" })
        ExitCode = $exitCode
        Required = $Required
        Output = $output
    }
}

Invoke-Step "compileall" { python -m compileall -q src/ms_preprocessing } $true
Invoke-Step "cli-version" { python main.py --version } $true

if (-not $Fast) {
    Invoke-Step "pytest" { pytest -q } $true
} else {
    Add-SkippedResult "pytest" "Skipped by -Fast"
}

if (-not $SkipRuff) {
    if (Get-Command ruff -ErrorAction SilentlyContinue) {
        Invoke-Step "ruff" { ruff check . } $false
    } else {
        Add-SkippedResult "ruff" "ruff is not installed"
    }
} else {
    Add-SkippedResult "ruff" "Skipped by -SkipRuff"
}

if ($Json) {
    $results | ConvertTo-Json -Depth 5
} else {
    $results | Select-Object Name, Status, ExitCode, Required | Format-Table -AutoSize
    foreach ($row in $results) {
        if ($row.Status -eq "fail") {
            Write-Host ""
            Write-Host "[$($row.Name)] output:"
            Write-Host $row.Output
        }
    }
}

if ($failedRequired) {
    exit 1
}
exit 0
