<#
  skills-hub —— Windows PowerShell 入口
  用法:  .\bin\skills-hub.ps1 status
#>

$ErrorActionPreference = 'Stop'

$BinDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $BinDir

function Resolve-Python {
    foreach ($candidate in @('python', 'python3', 'py')) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        try {
            $probe = 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)'
            $probeArgs = if ($candidate -eq 'py') { @('-3', '-c', $probe) } else { @('-c', $probe) }
            & $cmd.Source @probeArgs 2>$null
            if ($LASTEXITCODE -eq 0) {
                return @{ Exe = $cmd.Source; Prefix = if ($candidate -eq 'py') { @('-3') } else { @() } }
            }
        } catch { continue }
    }
    return $null
}

$py = Resolve-Python
if (-not $py) {
    Write-Error @"
skills-hub 需要 Python 3.9+，未在 PATH 中找到。
  winget install Python.Python.3.12
  或从 https://www.python.org/downloads/windows/ 安装（记得勾选 Add to PATH）
"@
    exit 1
}

$env:SKILLS_HUB_ROOT = if ($env:SKILLS_HUB_ROOT) { $env:SKILLS_HUB_ROOT } else { $RepoDir }
$env:PYTHONUTF8 = '1'
# 用 PYTHONPATH 而不是切换目录，保证 `skills-hub project .` 里的相对路径仍以用户当前目录为准
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$RepoDir;$env:PYTHONPATH" } else { $RepoDir }

& $py.Exe @($py.Prefix + @('-X', 'utf8', '-m', 'hub') + $args)
exit $LASTEXITCODE
