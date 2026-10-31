# Optional local installation; does not run the task immediately or change MT5.
param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$Name = 'OMNEX-AURA-Research-Operations'
if ($Remove) {
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    exit
}
$Root = Split-Path $PSScriptRoot -Parent
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Data = Join-Path $Root 'data'
if (!(Test-Path $Python)) { throw 'Install the project virtual environment first.' }
if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
    throw 'Task already exists. Review or remove it before registering a replacement.'
}
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Action = New-ScheduledTaskAction -Execute $Python -WorkingDirectory $Root -Argument "-m aura.operations --data-dir `"$Data`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'Research queue only. No collector or broker execution. Starts at interactive user logon.' | Out-Null
Write-Host 'Registered for next user logon. To start now: Start-ScheduledTask -TaskName OMNEX-AURA-Research-Operations'
