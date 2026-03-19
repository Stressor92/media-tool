<#
.SYNOPSIS
    Launcher script that ensures PowerShell 7 is used
.DESCRIPTION
    This script detects if it's running in PowerShell 7, and if not,
    relaunches itself with PowerShell 7 (pwsh.exe)
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$RootPath = "Y:\",
    
    [Parameter(Mandatory=$false)]
    [int]$MaxParallelJobs = 4
)

# Check if we're running in PowerShell 7+
if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Host "Currently running in PowerShell $($PSVersionTable.PSVersion)" -ForegroundColor Yellow
    Write-Host "Attempting to relaunch with PowerShell 7..." -ForegroundColor Cyan
    Write-Host ""
    
    # Try to find PowerShell 7
    $pwshPaths = @(
        "pwsh.exe",
        "C:\Program Files\PowerShell\7\pwsh.exe",
        "$env:ProgramFiles\PowerShell\7\pwsh.exe",
        "$env:LocalAppData\Microsoft\PowerShell\7\pwsh.exe"
    )
    
    $pwshFound = $null
    foreach ($path in $pwshPaths) {
        if (Get-Command $path -ErrorAction SilentlyContinue) {
            $pwshFound = $path
            break
        }
    }
    
    if ($pwshFound) {
        Write-Host "Found PowerShell 7 at: $pwshFound" -ForegroundColor Green
        Write-Host "Relaunching with PowerShell 7..." -ForegroundColor Green
        Write-Host ""
        
        # Relaunch this script with PowerShell 7
        $scriptPath = Join-Path $PSScriptRoot "Convert-MoviesToMKV-Optimized-Fixed.ps1"
        
        # Build arguments
        $arguments = @(
            "-ExecutionPolicy", "Bypass"
            "-NoProfile"
            "-File", "`"$scriptPath`""
            "-RootPath", "`"$RootPath`""
            "-MaxParallelJobs", "$MaxParallelJobs"
        )
        
        & $pwshFound @arguments
        exit $LASTEXITCODE
    } else {
        Write-Host "ERROR: PowerShell 7 not found!" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install PowerShell 7:" -ForegroundColor Yellow
        Write-Host "  winget install Microsoft.PowerShell" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Or download from:" -ForegroundColor Yellow
        Write-Host "  https://github.com/PowerShell/PowerShell/releases/latest" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Falling back to Windows PowerShell 5.1 (slower, no parallel)..." -ForegroundColor Yellow
        
        # Use the WinPS version instead
        $scriptPath = Join-Path $PSScriptRoot "Convert-MoviesToMKV-WinPS.ps1"
        & $scriptPath -RootPath $RootPath
        exit $LASTEXITCODE
    }
}

# We're already in PowerShell 7, run the conversion
Write-Host "Running in PowerShell $($PSVersionTable.PSVersion) - Perfect!" -ForegroundColor Green
Write-Host ""

$scriptPath = Join-Path $PSScriptRoot "Convert-MoviesToMKV-Optimized-Fixed.ps1"
& $scriptPath -RootPath $RootPath -MaxParallelJobs $MaxParallelJobs
