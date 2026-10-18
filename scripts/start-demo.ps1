param(
    [switch]$CheckOnly,
    [ValidateRange(1024, 65535)]
    [int]$Port = 8501
)

# Run in the foreground so Ctrl+C stops only the server started by this script.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$demoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$demoPython = Join-Path $demoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $demoPython -PathType Leaf)) {
    Write-Host 'Week2 Python is missing. Read docs/demo-guide.md before restoring its environment.'
    exit 1
}

Push-Location -LiteralPath $demoRoot
try {
    Write-Host 'Checking the existing local setup. No downloads, inference or Pinecone requests.'
    & $demoPython -m retail_copilot.demo_preflight --check-ollama
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Fix the CHECK item using docs/demo-guide.md, then try again.'
        exit 1
    }
    if ($CheckOnly) {
        Write-Host 'Checks finished. No Streamlit server was started or stopped.'
        exit 0
    }

    # A listening port does not prove which application owns it. Never reuse or kill it.
    $demoProbe = [System.Net.Sockets.TcpClient]::new()
    $demoPortOccupied = $false
    try {
        $demoProbe.Connect('127.0.0.1', $Port)
        $demoPortOccupied = $true
    }
    catch [System.Net.Sockets.SocketException] {
        if ($_.Exception.SocketErrorCode -ne [System.Net.Sockets.SocketError]::ConnectionRefused) {
            Write-Host 'Could not check the local port safely. See docs/demo-guide.md.'
            exit 1
        }
    }
    finally {
        $demoProbe.Dispose()
    }
    if ($demoPortOccupied) {
        Write-Host "Port $Port is already in use; no existing process was changed."
        Write-Host 'If your previous Week2 terminal is still running, use its browser address.'
        Write-Host 'Otherwise rerun this script with -Port 8502 (or another free port).'
        exit 1
    }

    Write-Host "Open http://127.0.0.1:$Port in your browser. Keep this terminal open; Ctrl+C stops this server."
    & $demoPython -m streamlit run (Join-Path $demoRoot 'app.py') --server.address 127.0.0.1 --server.port $Port --server.headless true
    exit $LASTEXITCODE
}
catch {
    Write-Host 'The local launcher could not finish. Check the project files and use docs/demo-guide.md; no existing process was stopped.'
    exit 1
}
finally {
    Pop-Location
}
