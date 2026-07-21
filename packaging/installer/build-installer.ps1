param(
    [switch]$SkipDependencyInstall,
    [switch]$SkipInno,
    [string]$InnoSetupCompiler = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$InstallerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $InstallerDir "..\..")
$PyDist = Join-Path $InstallerDir "dist"
$PyBuild = Join-Path $InstallerDir "build"
$AppDir = Join-Path $PyDist "VoiceCode"
$IssFile = Join-Path $InstallerDir "VoiceCode.iss"
$OutputDir = Join-Path $InstallerDir "Output"

Push-Location $RepoRoot
try {
    if (-not $SkipDependencyInstall) {
        python -m pip install -e ".[build]"
    }

    if (Test-Path $PyDist) { Remove-Item -Recurse -Force $PyDist }
    if (Test-Path $PyBuild) { Remove-Item -Recurse -Force $PyBuild }
    if (Test-Path $OutputDir) { Remove-Item -Recurse -Force $OutputDir }

    python -m PyInstaller `
        (Join-Path $InstallerDir "voicecode-onedir.spec") `
        --noconfirm `
        --distpath $PyDist `
        --workpath $PyBuild

    New-Item -ItemType Directory -Force -Path `
        (Join-Path $AppDir "runtime"), `
        (Join-Path $AppDir "runtime\cache"), `
        (Join-Path $AppDir "runtime\models") | Out-Null

    Write-Host "One-folder application built at: $AppDir"

    if ($SkipInno) {
        Write-Host "Skipping Inno Setup. You can distribute the one-folder build or run ISCC later."
        return
    }

    $iscc = $InnoSetupCompiler
    if (-not $iscc) {
        $candidateRoots = @(
            ${env:ProgramFiles(x86)},
            $env:ProgramFiles,
            (Join-Path $env:LOCALAPPDATA "Programs")
        ) | Where-Object { $_ }
        $candidates = foreach ($candidateRoot in $candidateRoots) {
            Join-Path $candidateRoot "Inno Setup 6\ISCC.exe"
        }
        $matchedCandidate = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($matchedCandidate) {
            $iscc = $matchedCandidate
        }
    }

    if (-not $iscc -or -not (Test-Path $iscc)) {
        Write-Warning "Inno Setup 6 compiler was not found. Install it or pass -InnoSetupCompiler."
        Write-Host "PyInstaller output is still ready at: $AppDir"
        return
    }

    & $iscc "/DSourceDir=$AppDir" $IssFile
    Write-Host "Installer output folder: $OutputDir"
}
finally {
    Pop-Location
}
