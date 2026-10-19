# Run with Windows PowerShell: powershell -NoProfile -File tests/test_setup_windows.ps1
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
. (Join-Path $repo 'setup-windows.ps1')
$base = Join-Path $repo ('.runtime\setup-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $base '.runtime') -Force | Out-Null
function Assert($condition, $message) { if (-not $condition) { throw $message } }

# Windows PowerShell 5.1 must emit each folder separately and deduplicate casing.
$folders = @(Read-DetectedGames '["d:\\steam\\steamapps\\common\\Valheim","D:\\Steam\\steamapps\\common\\Valheim","E:\\Steam Library\\steamapps\\common\\Valheim"]')
Assert ($folders.Count -eq 2) 'Duplicate or nested detection results.'
foreach ($folder in $folders) { Assert ($folder -is [string]) 'Detected folder must be one string argument.' }
Assert ($folders[1] -eq 'E:\Steam Library\steamapps\common\Valheim') 'Spaces in a folder were lost.'
Assert (@(Read-DetectedGames '[]').Count -eq 0) 'Empty detection must return no folders.'
Assert (@(Read-DetectedGames '["D:\\Valheim"]').Count -eq 1) 'One folder must remain one choice.'

# Declining Python must not download or launch anything.
function Confirm-Rune { return $false }
function Invoke-WebRequest { throw 'Unexpected network request' }
$result = Install-RunePython
Assert (-not $result) 'Declining setup must return no interpreter.'
Assert (-not (Test-Path (Join-Path $base 'runtime'))) 'Decline created a runtime.'

# Remember the icon Skip choice, with no package download.
Set-UpIcons 'not-a-python'
Assert (Test-Path (Join-Path $base '.runtime\icon-setup.json')) 'Icon skip was not remembered.'
function Confirm-Rune { throw 'Skip should suppress the next prompt.' }
Set-UpIcons 'not-a-python'

# A damaged download must never replace an existing runtime.
New-Item -ItemType Directory -Path (Join-Path $base 'runtime') | Out-Null
'original' | Set-Content (Join-Path $base 'runtime\keep.txt')
$script:answers = [System.Collections.Generic.Queue[bool]]::new()
$script:answers.Enqueue($true)
$script:answers.Enqueue($false)
function Confirm-Rune { return $script:answers.Dequeue() }
# Switch parameters must have the same binding behavior as the real cmdlet.
function Invoke-WebRequest { param([switch]$UseBasicParsing, $Uri, $OutFile, $TimeoutSec) 'wrong download' | Set-Content -LiteralPath $OutFile }
$result = Install-RunePython
Assert (-not $result) 'A bad hash was accepted.'
Assert ((Get-Content (Join-Path $base 'runtime\keep.txt')) -eq 'original') 'Existing runtime was changed.'
Write-Host 'Windows setup tests passed (decline, skip persistence, checksum failure, runtime preservation).'
