# Wolo One-Click Installation Script for Windows
# Usage: irm https://raw.githubusercontent.com/lzjever/wolo/main/scripts/install.ps1 | iex

$ErrorActionPreference = "Stop"

# Configuration
$RepoUrl = "https://github.com/lzjever/wolo"
$PythonMinVersion = [version]"3.10"
$PythonMaxVersion = [version]"3.15"
$WoloHome = if ($env:WOLO_HOME) { $env:WOLO_HOME } else { Join-Path $env:USERPROFILE ".wolo" }

# Color output functions
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Log-Info {
    Write-ColorOutput Cyan "[INFO] $args"
}

function Log-Success {
    Write-ColorOutput Green "[SUCCESS] $args"
}

function Log-Warn {
    Write-ColorOutput Yellow "[WARN] $args"
}

function Log-Error {
    Write-ColorOutput Red "[ERROR] $args"
}

function Test-PythonVersion {
    param([string]$PythonPath)

    try {
        $versionOutput = & $PythonPath --version 2>&1
        if ($versionOutput -match "Python (\d+\.\d+\.\d+)") {
            $version = [version]$matches[1]
            return $version
        }
    }
    catch {
        return $null
    }
    return $null
}

function Find-Python {
    Log-Info "Searching for Python installation..."

    # Check python command
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $version = Test-PythonVersion "python"
        if ($version -ge $PythonMinVersion -and $version -lt ([version]"3.16")) {
            Log-Success "Found Python $version at python"
            return "python"
        }
    }

    # Check python3 command
    $python3Cmd = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3Cmd) {
        $version = Test-PythonVersion "python3"
        if ($version -ge $PythonMinVersion -and $version -lt ([version]"3.16")) {
            Log-Success "Found Python $version at python3"
            return "python3"
        }
    }

    # Check py launcher
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        # Try to find a suitable version
        $versions = & py --list 2>&1
        if ($versions -match "-V:(\d+\.\d+)") {
            foreach ($line in $versions) {
                if ($line -match "-V:(\d+)\.(\d+)") {
                    $major = $matches[1]
                    $minor = $matches[2]
                    $verStr = "$major.$minor"
                    $version = [version]"$verStr.0"
                    if ($version -ge $PythonMinVersion -and $major -lt 4) {
                        Log-Success "Found Python $verStr via py launcher"
                        return "py -$major.$minor"
                    }
                }
            }
        }
    }

    # Check common installation paths
    $commonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:PROGRAMFILES\Python3*\python.exe",
        "$env:PROGRAMFILES\Python39\python.exe",
        "$env:PROGRAMFILES\Python310\python.exe",
        "$env:PROGRAMFILES\Python311\python.exe",
        "$env:PROGRAMFILES\Python312\python.exe",
        "$env:PROGRAMFILES\Python313\python.exe",
        "$env:APPDATA\Python\Python3*\python.exe"
    )

    foreach ($path in $commonPaths) {
        $resolved = Resolve-Path $path -ErrorAction SilentlyContinue
        if ($resolved) {
            $version = Test-PythonVersion $resolved.Path
            if ($version -ge $PythonMinVersion -and $version -lt ([version]"3.16")) {
                Log-Success "Found Python $version at $($resolved.Path)"
                return $resolved.Path
            }
        }
    }

    Log-Error "Python $PythonMinVersion or higher not found!"
    Log-Info "Please install Python from: https://www.python.org/downloads/"
    Log-Info "Make sure to check 'Add Python to PATH' during installation."
    exit 1
}

function Install-ViaPip {
    param([string]$PythonCmd)

    Log-Info "Installing wolo via pip..."

    # Check if pip is available
    $pipCheck = & $PythonCmd -m pip --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Log-Error "pip is not available. Please install Python with pip included."
        exit 1
    }

    # Install wolo
    & $PythonCmd -m pip install --upgrade mbos-wolo

    if ($LASTEXITCODE -eq 0) {
        Log-Success "wolo installed successfully"
        return "python -m wolo"
    } else {
        Log-Error "Failed to install wolo"
        exit 1
    }
}

function Install-ViaUv {
    param([string]$PythonCmd)

    Log-Info "Installing wolo via uv..."

    # Check if uv is installed
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue

    if (-not $uvCmd) {
        Log-Info "Installing uv..."
        $uvInstallUrl = "https://astral.sh/uv/install.ps1"
        Invoke-RestMethod -Uri $uvInstallUrl | Invoke-Expression

        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    }

    if ($uvCmd) {
        Log-Success "uv is available"

        # Create virtual environment
        $venvPath = Join-Path $WoloHome "venv"
        New-Item -ItemType Directory -Force -Path $WoloHome | Out-Null

        Log-Info "Creating virtual environment at $venvPath..."
        & uv venv $venvPath

        Log-Info "Installing wolo..."
        & uv pip install -U mbos-wolo --python "$venvPath\Scripts\python.exe"

        # Create wrapper script
        $wrapperDir = Join-Path $env:USERPROFILE "bin"
        New-Item -ItemType Directory -Force -Path $wrapperDir | Out-Null

        $wrapperPath = Join-Path $wrapperDir "wolo.ps1"
        @"
@echo off
`$WOLO_HOME = if (`$env:WOLO_HOME) { `$env:WOLO_HOME } else { Join-Path `$env:USERPROFILE ".wolo" }
`$venvPython = Join-Path `$WOLO_HOME "venv\Scripts\python.exe"
if (Test-Path `$venvPython) {
    & `$venvPython -m wolo `$args
} else {
    Write-Error "Error: wolo is not installed properly. Please run the installer again."
    exit 1
}
"@ | Out-File -FilePath $wrapperPath -Encoding UTF8

        # Create batch file for CMD
        $batchPath = Join-Path $wrapperDir "wolo.bat"
        @"
@echo off
set WOLO_HOME=%USERPROFILE%\.wolo
"%WOLO_HOME%\venv\Scripts\python.exe" -m wolo %*
"@ | Out-File -FilePath $batchPath -Encoding ASCII

        Log-Success "wolo installed via uv"

        # Add to PATH reminder
        $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
        if ($userPath -notlike "*$wrapperDir*") {
            Log-Warn "$wrapperDir is not in PATH. Add it manually or restart your terminal."
        }

        return "wolo"
    } else {
        Log-Warn "uv installation failed. Falling back to pip."
        return Install-ViaPip $PythonCmd
    }
}

function Install-FromSource {
    param([string]$PythonCmd)

    Log-Info "Installing wolo from source..."

    $tempDir = Join-Path $env:TEMP "wolo-install"
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

    Push-Location $tempDir

    try {
        # Check for git
        $gitCmd = Get-Command git -ErrorAction SilentlyContinue
        if (-not $gitCmd) {
            Log-Error "git is not installed. Please install Git from: https://git-scm.com/download/win"
            exit 1
        }

        Log-Info "Cloning repository..."
        & git clone --depth 1 $RepoUrl wolo-temp
        Set-Location wolo-temp

        Log-Info "Building and installing..."
        & $PythonCmd -m pip install build
        & $PythonCmd -m build
        & $PythonCmd -m pip install dist\*.whl

        Pop-Location
        Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue

        Log-Success "wolo installed from source"
        return "wolo"
    }
    catch {
        Pop-Location
        Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
        Log-Error "Installation from source failed: $_"
        exit 1
    }
}

function Verify-Installation {
    param([string]$PythonCmd)

    Log-Info "Verifying installation..."

    $versionOutput = & $PythonCmd -m wolo --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Log-Success "wolo is installed and working!"
        Log-Info "Version: $versionOutput"
        return $true
    } else {
        Log-Error "Installation verification failed"
        return $false
    }
}

function Show-PostInstall {
    Write-Host ""
    Log-Success "Wolo installation complete!"
    Write-Host ""
    Write-Host "Quick Start:" -ForegroundColor Cyan
    Write-Host "  wolo `"your prompt here`"    # Run a task"
    Write-Host "  wolo chat                   # Start interactive mode"
    Write-Host "  wolo config init            # First-time setup"
    Write-Host ""
    Write-Host "Configuration:" -ForegroundColor Cyan
    Write-Host "  Config file: $env:USERPROFILE\.wolo\config.yaml"
    Write-Host "  Set API key: `$env:WOLO_API_KEY = `"your-key-here`""
    Write-Host ""
    Write-Host "For more information:" -ForegroundColor Cyan
    Write-Host "  GitHub: $RepoUrl"
    Write-Host "  Docs:   https://github.com/lzjever/wolo#readme"
    Write-Host ""
}

# Main installation flow
function Main {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║              Wolo One-Click Installer                 ║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""

    # Find Python
    $pythonCmd = Find-Python

    # Determine installation method
    $installMethod = if ($env:WOLO_INSTALL_METHOD) { $env:WOLO_INSTALL_METHOD } else { "auto" }

    if ($installMethod -eq "auto") {
        $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
        if ($uvCmd) {
            $installMethod = "uv"
        } else {
            $installMethod = "pip"
        }
    }

    Log-Info "Installation method: $installMethod"

    # Install
    switch ($installMethod) {
        "uv" {
            $woloCmd = Install-ViaUv $pythonCmd
        }
        "pip" {
            $woloCmd = Install-ViaPip $pythonCmd
        }
        "source" {
            $woloCmd = Install-FromSource $pythonCmd
        }
        default {
            Log-Error "Unknown installation method: $installMethod"
            exit 1
        }
    }

    # Verify
    $verified = Verify-Installation $pythonCmd

    if ($verified) {
        Show-PostInstall
    } else {
        Log-Error "Installation completed but verification failed."
        Log-Info "Please check your Python installation and try again."
        exit 1
    }
}

# Run main function
Main
