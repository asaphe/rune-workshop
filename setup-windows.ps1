param([switch]$ConfigureIcons)
$ErrorActionPreference = 'Stop'
$base = $PSScriptRoot
Set-Location -LiteralPath $base
$env:PYTHONHOME = ''
$env:PYTHONPATH = ''

function Confirm-Rune([string]$Message) {
    return (Read-Host "$Message [y/N]") -match '^(y|yes)$'
}

function Find-RunePython {
    $portable = Join-Path $base 'runtime\python.exe'
    if (Test-Path -LiteralPath $portable) {
        try {
            & $portable -E -s (Join-Path $base 'launch.py') --check *> $null
            if ($LASTEXITCODE -eq 0) { return $portable }
        } catch { Write-Host 'The existing portable Python could not start.' }
    }
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        try {
            $candidate = & py.exe -3 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Path -LiteralPath $candidate)) {
                & $candidate -E -s (Join-Path $base 'launch.py') --check *> $null
                if ($LASTEXITCODE -eq 0) { return $candidate }
            }
        } catch { Write-Host 'The installed Python could not start.' }
    }
    return $null
}

function Install-RunePython([string]$RuntimeFolder = 'runtime') {
    # Official CPython release manifest, checked 2026-10-19. Use a supported
    # stable release with wheels available for the optional icon extractor.
    $version = '3.14.8'
    $arch = $env:PROCESSOR_ARCHITEW6432
    if (-not $arch) { $arch = $env:PROCESSOR_ARCHITECTURE }
    $packages = @{
        AMD64 = @('amd64', '80292f0e640e373a54bf09f3b94a1472f976f24a10c5bed0d9622e4e44d67447')
        ARM64 = @('arm64', '3d5cf5f4ec055b1dc2882fe6fbaaeb483d1984dd5335ae9ac692e0c6b3ce8785')
        x86 = @('win32', '06ec9bc608edcce83af25efe48cdb6d9146469ee1f0c86f215fa019dc72c7aa4')
    }
    if (-not $packages.ContainsKey($arch)) { throw "Unsupported Windows architecture: $arch. See README.md for manual setup." }
    $package = $packages[$arch]
    $url = "https://www.python.org/ftp/python/$version/python-$version-embeddable-$($package[0]).zip"
    Write-Host "Automatic setup downloads official Python $version from python.org into $RuntimeFolder."
    Write-Host 'It stays in this Rune folder. No administrator access or system installation is needed.'
    if (-not (Confirm-Rune 'Download and set up portable Python?')) { return $null }
    while ($true) {
        try {
            $stage = Join-Path $base ('.runtime\setup-' + [guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Path $stage -Force | Out-Null
            $zip = Join-Path $stage 'python.zip'
            $unpacked = Join-Path $stage 'runtime'
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Write-Host 'Downloading Python...'
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $zip -TimeoutSec 120
            if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $package[1]) { throw 'Python download checksum mismatch. Nothing was installed.' }
            Expand-Archive -LiteralPath $zip -DestinationPath $unpacked
            $candidate = Join-Path $unpacked 'python.exe'
            & $candidate -E -s (Join-Path $base 'launch.py') --check | Out-Host
            if ($LASTEXITCODE -ne 0) { throw 'The downloaded Python failed its startup check.' }
            $destination = Join-Path $base $RuntimeFolder
            $previous = $null
            if (Test-Path -LiteralPath $destination) {
                $previous = Join-Path $stage 'previous-runtime'
                Move-Item -LiteralPath $destination -Destination $previous
                Write-Host "Previous runtime retained at $previous"
            }
            try {
                Move-Item -LiteralPath $unpacked -Destination $destination
            } catch {
                if ($previous -and -not (Test-Path -LiteralPath $destination)) {
                    Move-Item -LiteralPath $previous -Destination $destination
                }
                throw
            }
            return (Join-Path $destination 'python.exe')
        } catch {
            Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Yellow
            if (-not (Confirm-Rune 'Retry Python setup?')) { return $null }
        }
    }
}

function Read-DetectedGames([string]$Json) {
    # Windows PowerShell 5.1 emits a JSON array as one pipeline object. Enumerate
    # explicitly before collecting results, otherwise two folders become one argv.
    $folders = foreach ($folder in (ConvertFrom-Json -InputObject $Json)) {
        if ($folder -isnot [string]) { throw 'Unexpected Valheim detection result.' }
        $folder
    }
    $folders | Sort-Object -Unique
}

function Set-UpIcons([string]$Python) {
    $marker = Join-Path $base '.runtime\icon-setup.json'
    $icons = Join-Path $base 'backend\local-data\item_icons'
    if (-not $ConfigureIcons -and ((Test-Path -LiteralPath $marker) -or (Get-ChildItem -LiteralPath $icons -Filter '*.png' -ErrorAction SilentlyContinue | Select-Object -First 1))) { return }
    Write-Host ''
    Write-Host 'Optional: show item pictures from your installed copy of Valheim.'
    Write-Host 'This downloads UnityPy and its dependencies from PyPI into Rune, then reads your game artwork.'
    Write-Host 'Your game and saves are not modified. You can skip this and use placeholder icons.'
    if (-not (Confirm-Rune 'Set up item pictures?')) {
        '{"status":"skipped"}' | Set-Content -LiteralPath $marker -Encoding ASCII
        return
    }
    $version = & $Python -E -s -c 'import sys; print(sys.version_info.minor)'
    if ([int]$version -gt 14) {
        Write-Host 'The artwork tools do not yet support this Python. They need a separate portable runtime.'
        $iconPython = Join-Path $base '.runtime\icon-runtime\python.exe'
        if (-not (Test-Path -LiteralPath $iconPython)) { $iconPython = Install-RunePython '.runtime\icon-runtime' }
        if (-not $iconPython) { return }
        $Python = $iconPython
    }
    while ($true) {
        try {
            $detectionJson = & $Python -E -s (Join-Path $base 'setup_icons.py') --detect
            if ($LASTEXITCODE -ne 0) { throw 'Could not search for Valheim installations.' }
            $detected = @(Read-DetectedGames ($detectionJson -join "`n"))
            $game = $null
            foreach ($folder in $detected) {
                if (Confirm-Rune "Use Valheim at $folder ?") { $game = $folder; break }
            }
            if (-not $game) {
                Add-Type -AssemblyName System.Windows.Forms
                $picker = New-Object System.Windows.Forms.OpenFileDialog
                try {
                    $picker.Title = 'Choose valheim.exe in your Valheim installation (Cancel to skip)'
                    $picker.Filter = 'Valheim executable (valheim.exe)|valheim.exe'
                    if ($picker.ShowDialog() -ne 'OK') { return }
                    $game = Split-Path -LiteralPath $picker.FileName
                } finally { $picker.Dispose() }
            }
            & $Python -E -s (Join-Path $base 'setup_icons.py') --game $game
            if ($LASTEXITCODE -ne 0) { throw 'Icon extraction did not finish. Your existing artwork was retained.' }
            '{"status":"complete"}' | Set-Content -LiteralPath $marker -Encoding ASCII
            return
        } catch {
            Write-Host "Item pictures: $($_.Exception.Message)" -ForegroundColor Yellow
            Write-Host 'Rune can still run with placeholder icons. Use Setup Rune.cmd to try again later.'
            if (-not (Confirm-Rune 'Retry item picture setup?')) { return }
        }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
try {
    New-Item -ItemType Directory -Force -Path (Join-Path $base '.runtime') | Out-Null
    $python = Find-RunePython
    if (-not $python) { $python = Install-RunePython }
    if (-not $python) {
        Write-Host 'Setup cancelled. Nothing was launched. See README.md for manual Python setup.'
        exit 1
    }
    Set-UpIcons $python
    $pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
    if (-not (Test-Path -LiteralPath $pythonw)) { $pythonw = $python }
    Start-Process -FilePath $pythonw -ArgumentList @('-E', '-s', ('"' + (Join-Path $base 'launch.py') + '"')) -WorkingDirectory $base -WindowStyle Hidden
} catch {
    Write-Host "Rune setup failed: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host 'Press Enter to close' | Out-Null
    exit 1
}

}
