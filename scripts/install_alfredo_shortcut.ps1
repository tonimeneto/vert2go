$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$pythonPath = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$scriptPath = Join-Path $projectRoot 'scripts\alfredo_control.py'
if (!(Test-Path -LiteralPath $pythonPath) -or !(Test-Path -LiteralPath $scriptPath)) {
    throw 'Ambiente do Alfredo incompleto.'
}
$desktopPath = [Environment]::GetFolderPath('DesktopDirectory')
if (!$desktopPath -or !(Test-Path -LiteralPath $desktopPath -PathType Container)) {
    throw 'Area de trabalho nao encontrada.'
}
$shortcutPath = Join-Path $desktopPath 'Alfredo - Ligar e desligar.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$arguments = '-B "' + $scriptPath + '"'
if ((Test-Path -LiteralPath $shortcutPath) -and
    ($shortcut.TargetPath -ne $pythonPath -or $shortcut.Arguments -ne $arguments)) {
    throw 'Ja existe um atalho diferente com esse nome; ele foi preservado.'
}
$shortcut.TargetPath = $pythonPath
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Controle do Alfredo: ligar, desligar e acompanhar o estado.'
$shortcut.IconLocation = $pythonPath + ',0'
$shortcut.WindowStyle = 1
$shortcut.Save()
$verified = $shell.CreateShortcut($shortcutPath)
if ($verified.TargetPath -ne $pythonPath -or $verified.Arguments -ne $arguments -or
    $verified.WorkingDirectory -ne $projectRoot) { throw 'Atalho nao conferiu.' }
[pscustomobject]@{Shortcut=$shortcutPath;Target=$verified.TargetPath;Arguments=$verified.Arguments;WorkingDirectory=$verified.WorkingDirectory} | ConvertTo-Json -Compress
