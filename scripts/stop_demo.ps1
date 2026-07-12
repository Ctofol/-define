param(
    [int[]]$Ports = @(8000, 5173)
)

$ErrorActionPreference = "SilentlyContinue"

foreach ($Port in $Ports) {
    $Connections = Get-NetTCPConnection -LocalPort $Port -State Listen
    foreach ($Connection in $Connections) {
        $ProcessId = $Connection.OwningProcess
        $Process = Get-Process -Id $ProcessId
        if ($Process) {
            Write-Host "Stopping $($Process.ProcessName) on port $Port (PID $ProcessId)"
            Stop-Process -Id $ProcessId -Force
        }
    }
}
