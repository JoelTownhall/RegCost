# PowerShell script to create scheduled task with proper repetition

$taskName = "RegCost_API_Update"
$pythonPath = "C:\Users\joelr\AppData\Local\Microsoft\WindowsApps\python.exe"
$scriptPath = "C:\Users\joelr\projects\regcost\scheduled_api_update.py"

# Remove existing task if it exists
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Create the action
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $scriptPath -WorkingDirectory "C:\Users\joelr\projects\regcost"

# Create trigger with repetition using the proper method
$trigger = New-ScheduledTaskTrigger -Once -At "8:00PM" -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration (New-TimeSpan -Hours 48)

# Create settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register the task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Fetch API metadata for legislation.gov.au - retries every 2 hours until successful"

Write-Host ""
Write-Host "Task '$taskName' created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Schedule:"
Write-Host "  - Starts: 8:00 PM today"
Write-Host "  - Repeats: Every 2 hours"
Write-Host "  - Duration: 48 hours (covers the weekend)"
Write-Host ""
Write-Host "The task will stop retrying once api_update_complete.json is created."
Write-Host "Check progress in: C:\Users\joelr\projects\regcost\logs\api_update.log"
Write-Host ""

# Show task info
Get-ScheduledTask -TaskName $taskName | Format-List TaskName, State
$taskInfo = Get-ScheduledTaskInfo -TaskName $taskName
Write-Host "Next run time: $($taskInfo.NextRunTime)"
