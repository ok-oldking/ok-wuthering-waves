param(
    [ValidateSet('main_debug.py', 'main.py')]
    [string]$EntryPoint = 'main_debug.py',
    [string]$LogPath
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$projectPath = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
Set-Location -LiteralPath $projectPath
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Project Python was not found: $pythonPath"
}

# The elevated launcher merges stdout and stderr into a file the terminal can read.
if ($LogPath) {
    $captureCode = @'
import os
import subprocess
import sys
import time

with open(sys.argv[1], 'ab', buffering=0) as output:
    process = subprocess.Popen(
        [sys.executable, '-X', 'utf8', '-u', sys.argv[2]],
        stdout=output, stderr=subprocess.STDOUT,
    )
    try:
        while process.poll() is None:
            if os.path.exists(sys.argv[1] + '.stop'):
                process.terminate()
                break
            time.sleep(0.1)
        result = process.wait()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()
sys.exit(result)
'@
    & $pythonPath -X utf8 -u -c $captureCode $LogPath $EntryPoint
    exit $LASTEXITCODE
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    & $pythonPath -X utf8 -u (Join-Path $projectPath $EntryPoint)
    exit $LASTEXITCODE
}

$outputPath = [IO.Path]::GetTempFileName()
$reader = $null
$elevatedProcess = $null
$exitCode = 1
try {
    # Encode the command so paths with spaces and quotes survive UAC relaunch.
    $quotedScript = $PSCommandPath.Replace("'", "''")
    $quotedOutput = $outputPath.Replace("'", "''")
    $command = "& '$quotedScript' -EntryPoint '$EntryPoint' -LogPath '$quotedOutput'; exit `$LASTEXITCODE"
    $encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
    Write-Host 'Requesting administrator access; app logs will appear here.'
    $powershellPath = (Get-Command powershell.exe -CommandType Application).Source
    $elevatedProcess = Start-Process -FilePath $powershellPath `
        -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encodedCommand `
        -WorkingDirectory $projectPath -Verb RunAs -WindowStyle Hidden -PassThru

    $stream = [IO.File]::Open($outputPath, [IO.FileMode]::Open,
        [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    $reader = [IO.StreamReader]::new($stream, [Text.Encoding]::UTF8)
    while (-not $elevatedProcess.HasExited) {
        [Console]::Write($reader.ReadToEnd())
        Start-Sleep -Milliseconds 100
    }
    [Console]::Write($reader.ReadToEnd())
    $elevatedProcess.WaitForExit()
    $exitCode = $elevatedProcess.ExitCode
}
finally {
    # Let the elevated wrapper stop its own child when Ctrl+C stops this launcher.
    if ($elevatedProcess -and -not $elevatedProcess.HasExited) {
        [IO.File]::WriteAllText("$outputPath.stop", '')
        $null = $elevatedProcess.WaitForExit(5000)
    }
    if ($reader) { $reader.Dispose() }
    if (-not $elevatedProcess -or $elevatedProcess.HasExited) {
        [IO.File]::Delete($outputPath)
        [IO.File]::Delete("$outputPath.stop")
    }
    if ($elevatedProcess) { $elevatedProcess.Dispose() }
}
exit $exitCode
