<#
  日本郵船 株価予測レポートを Windows タスク スケジューラに登録する。
  既定: 平日（月〜金）18:15 に run_scheduled.cmd を実行。

  使い方（PowerShell）:
    powershell -ExecutionPolicy Bypass -File .\register_task.ps1
    powershell -ExecutionPolicy Bypass -File .\register_task.ps1 -Time 19:00
    powershell -ExecutionPolicy Bypass -File .\register_task.ps1 -Unregister

  管理者権限は不要（現在のユーザーのタスクとして登録）。
#>
param(
    [string]$Time = "18:15",
    [string]$TaskName = "NYK-StockForecast",
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$cmd  = Join-Path $root "run_scheduled.cmd"

if ($Unregister) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "タスク '$TaskName' を削除しました。"
    } else {
        Write-Host "タスク '$TaskName' は存在しません。"
    }
    return
}

if (-not (Test-Path $cmd)) { throw "run_scheduled.cmd が見つかりません: $cmd" }

$action  = New-ScheduledTaskAction -Execute $cmd -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $Time
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -RunOnlyIfNetworkAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description "日本郵船(9101.T)の株価予測レポートを生成する" | Out-Null

Write-Host "タスク '$TaskName' を登録しました（平日 $Time 実行）。"
Write-Host "レポート出力先: $(Join-Path $root 'output\report_latest.html')"
Write-Host ""
Write-Host "今すぐ試験実行するには:"
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
