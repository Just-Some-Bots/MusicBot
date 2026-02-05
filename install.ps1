# This script is designed to be used without pulling the repository first!
# You can simply download and run it to have MusicBot installed for you.
# Currently the script only supports one installation per user account.
#
# Notice:
#  If you want to run this .ps1 script without setting execution policy in PowerShell,
#  you can make use of the following command in command-prompt.
#
#    powershell.exe -noprofile -executionpolicy bypass -file install.ps1
#
# Last tested:
#  Win 10 Home 22H2 x64 - 2024/09/26
# --------------------------------------------------CLI Parameters-----------------------------------------------------
param (
    # -anybranch  Enables the use of any named branch, if it exists on repo.
    [switch]$anybranch = $false,
    [switch]$auto = $false,
    [string]$branch = ""
)
# Where to put MusicBot by default.  Updated by repo detection.
# prolly should be param, but someone who cares about windows can code for it.
$Install_Dir = (Get-Location).Path + '\MusicBot\'

# --------------------------------------------------Functions----------------------------------------------------------

function AskInput {
    $prompt = $args[0]
    $defval = $args[1]
    if ($auto) {
        Write-Information "${prompt}: $defval"
        return $defval
    }
    $userInput = Read-Host "$prompt"
    return $userInput
}

function ErrorExit {
    $message = if ($args.Count -ge 1) { $args[0] } else { "Error. Install halted." }
    $exitCode = if ($args.Count -ge 2) { $args[1] } else { 1 }

    Write-Information $message
    exit $exitCode
}

function wgInstall {
    $command = "winget install $args"
    if ($auto) {
        $command += " --silent"
    }
    Write-Information "Running:  $command"
    Invoke-Expression $command
}


# ---------------------------------------------Install notice and prompt-----------------------------------------------
"MusicBot Installer"
""
"MusicBot and this installer are provided under an MIT license."
"This software is provided 'as is' and may not be fit for any particular use, stated or otherwise."
"Please read the LICENSE file for full details."
""
"This installer attempts to provide automatic install for MusicBot and dependencies."
"It is recommended that you personally check the installer script before running it,"
"and verify the steps for your OS version are correct."
""
"Please consider contributing corrections or new steps if you find issues with this installer."
"You may also find installation guides on the wiki or community help on our discord server."
"Wiki:"
"    https://just-some-bots.github.io/MusicBot/"
"Discord:"
"    https://discord.gg/bots"
""

$iagree = AskInput "Would you like to continue with the install? [Y/n]" "y"
if($iagree -ne "Y" -and $iagree -ne "y")
{
    # exit early if the user does not want to continue.
    Return
}

# ensure $auto implies any

# First, unhide file extensions...
$FERegPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced'
$HideExt = (Get-ItemProperty -Path $FERegPath -Name "HideFileExt").HideFileExt
if ($HideExt -eq 1) {
    ""
    "Microsoft hates you and hides file extensions by default."
    "We're going to un-hide them to make things less confusing."
    Set-ItemProperty -Name "HideFileExt" -Value 0 -Path $FERegPath -Force
}

# If no winget, try to download and install.
if (-Not (Get-Command winget -ErrorAction SilentlyContinue) )
{
    ""
    "Microsoft WinGet tool is required to continue installing."
    "It will be downloaded from:"
    "  https://aka.ms/getwinget  "
    ""
    "Please complete the Windows installer when prompted."
    ""

    # download and run the installer.
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri "https://aka.ms/getwinget" -OutFile "winget.msixbundle"
    $ProgressPreference = 'Continue'
    Add-AppxPackage "winget.msixbundle"

    # if the above fails, fall back to the more manual way...
    if (-Not (Get-Command winget -ErrorAction SilentlyContinue) ) {
        "... Trying a more manual install for winget..."
        "Downloading winget & dependencies..."
        Invoke-WebRequest -Uri "https://github.com/microsoft/winget-cli/releases/latest/download/Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle" -OutFile "WinGet.msixbundle"
        Invoke-WebRequest -Uri "https://github.com/microsoft/winget-cli/releases/latest/download/DesktopAppInstaller_Dependencies.zip" -OutFile "DesktopAppInstaller_Dependencies.zip"
        Invoke-WebRequest -Uri "https://github.com/microsoft/winget-cli/releases/latest/download/e53e159d00e04f729cc2180cffd1c02e_License1.xml" -OutFile "license.xml"
        "Unpacking dependencies..."
        Expand-Archive -Path "DesktopAppInstaller_Dependencies.zip"
        "Installing dependencies..."
        " - Installing UI Xaml ..."
        Add-AppxPackage "DesktopAppInstaller_Dependencies\x64\Microsoft.UI.Xaml*x64.appx"
        " - Installing VC Libs ..."
        Add-AppxPackage "DesktopAppInstaller_Dependencies\x64\Microsoft.VCLibs*x64.appx"
        " - Installing Windows App Runtime ..."
        Add-AppxPackage "DesktopAppInstaller_Dependencies\x64\Microsoft.WindowsAppRuntime*x64.appx"
        "Installing winget..."
        Add-AppxProvisionedPackage -Online -PackagePath "WinGet.msixbundle" -LicensePath "license.xml"
        Get-AppPackage *Microsoft.DesktopAppInstaller*|Select-Object Name,PackageFullName
        Remove-Item -Path "WinGet.msixbundle", "DesktopAppInstaller_Dependencies.zip", "DesktopAppInstaller_Dependencies", "license.xml" -Recurse -Force
    }

    # check if winget is available post-install.
    if (-Not (Get-Command winget -ErrorAction SilentlyContinue) ) {
        ErrorExit "WinGet is not available.  Installer cannot continue."
        Return
    }
}


""
"Checking WinGet can be used..."
"If prompted, you must agree to the MS terms to continue installing."
""
winget list -q Git.Git
""

# since windows is silly with certificates and certifi may not always work,
# we queitly spawn some requests that -may- populate the certificate store.
# this isn't a sustainable approach, but it seems to work...
$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest -Uri "https://discord.com" -OutFile "cert.fetch" 2>&1 | Out-Null
Invoke-WebRequest -Uri "https://spotify.com" -OutFile "cert.fetch" 2>&1 | Out-Null
$ProgressPreference = 'Continue'
Remove-Item "cert.fetch"

# -----------------------------------------------------CONSTANTS-------------------------------------------------------

$MB_RepoURL = "https://github.com/Just-Some-Bots/MusicBot.git"

# ----------------------------------------------INSTALLING DEPENDENCIES------------------------------------------------
$NeedsEnvReload = 0

# Check if git is installed
"Checking if git is already installed..."
Invoke-Expression "winget list -q Git.Git" | Out-Null
if (!($LastExitCode -eq 0))
{
    # install git
    "Installing git..."
    wgInstall "Git.Git"
    $NeedsEnvReload = 1
    "Done."
}
else
{
    "Git already installed."
}
""

# Check if Any python 3 is installed
"Checking if python 3 is already installed..."
Invoke-Expression "winget list -q Python.Python.3" | Out-Null
if (!($LastExitCode -eq 0))
{
    # install python version 3.11 with the py.exe launcher.
    "Installing python..."
    wgInstall "Python.Python.3.11 --custom \`"/passive Include_launcher=1\`""
    $NeedsEnvReload = 1
    "Done."
}
else
{
    "Python 3 already installed."
}
""

# Check if ffmpeg is installed
"Checking if FFmpeg is already installed..."
Invoke-Expression "winget list -q ffmpeg" | Out-Null
if (!($LastExitCode -eq 0))
{
    # install FFmpeg
    "Installing FFmpeg..."
    wgInstall "ffmpeg"
    $NeedsEnvReload = 1
    "Done."
}
else
{
    "FFmpeg already installed."
}
""

# Check if deno is installed
"Checking if deno is already installed..."
Invoke-Expression "winget list -q deno" | Out-Null
if (!($LastExitCode -eq 0))
{
    # install deno js runtime
    "Installing deno..."
    wgInstall "--id=DenoLand.Deno"
    $NeedsEnvReload = 1
    "Done."
}
else
{
    "deno already installed."
}
""

# try to reload environment variables...
if ($NeedsEnvReload -eq 1)
{
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# --------------------------------------------------PULLING THE BOT----------------------------------------------------

# Test if we need to pull the bot or not by checking for some files.
$MB_Reqs_File=(Get-Location).Path + '\requirements.txt'
$MB_Module_Dir=(Get-Location).Path + '\musicbot'
$MB_Git_Dir=(Get-Location).Path + '\.git'

if((Test-Path $MB_Reqs_File) -and (Test-Path $MB_Module_Dir) -and (Test-Path $MB_Git_Dir) ) {
    ""
    "Installer detected an existing clone, and will continue installing with the current source."
    ""
    $Install_Dir = (Get-Location).Path
} else {
    ""
    "MusicBot currently has three branches available."
    "  master - Stable MusicBot, least updates and may at times be out-of-date."
    "  review - Newer MusicBot, usually stable with less updates than the dev branch."
    "  dev    - The newest MusicBot, latest features and changes which may need testing."
    if($anybranch) {
    "   *     - WARNING: Any branch name is allowed, if it exists on github."
    }
    ""
    $experimental = AskInput "Enter the branch name you want to install" "$branch"
    $experimental = $experimental.Trim()
    switch($experimental) {
        "dev" {
            "Installing dev branch..."
            $branch = "dev"
        }
        "review" {
            "Installing review branch..."
            $branch = "review"
        }
        default {
            if($anybranch -and $experimental -and $experimental -ne "master")
            {
                "Installing with $experimental branch, if it exists..."
                $branch = $experimental
            }
            else
            {
                "Installing master branch..."
                $branch = "master"
            }
        }
    }

    Invoke-Expression "git clone $MB_RepoURL '$Install_Dir' -b $branch"
    Invoke-Expression "cd '$Install_Dir'"
    ""
}

# --------------------------------------------INSTALL PYTHON DEPENDENCIES----------------------------------------------

if (Get-Command "python" -errorAction SilentlyContinue)
{
    Invoke-Expression "python -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)'" | Out-Null
    if($LastExitCode -eq 0)
    {
        $PYTHON = "python"
    }
}

$versionArray = "3.10", "3.11", "3.12", "3.13"

foreach ($version in $versionArray)
{
    Invoke-Expression "py -$version -c 'exit()' 2>&1" | Out-Null
    if($LastExitCode -eq 0)
    {
        $PYTHON = "py -$version"
    }
}

"Using $PYTHON to install and run MusicBot..."
""
Invoke-Expression "$PYTHON -m pip install --upgrade -r requirements.txt"

# -------------------------------------------------CONFIGURE THE BOT---------------------------------------------------
""
"MusicBot is almost ready to run, we just need to configure the bot."
"This installer provides an automated, but minimal, guided configuration."
"It will ask you to enter a bot token."
""
$iagree = AskInput "Would you like to continue with configuration? [y/N]" "n"
if($iagree -ne "Y" -and $iagree -ne "y")
{
    "All done!"
    "Remember to configure your bot token and other options before you start."
    "You must open a new command prompt before using run.bat to start the MusicBot."
    "MusicBot was installed to:"
    "  $Install_Dir"
    Return
}


Copy-Item ".\config\example_options.ini" -Destination ".\config\options.ini"

"Copied example_options.ini to options.ini"
"Starting configure.py configuration tool..."

Invoke-Expression "$PYTHON configure.py"

"You can use run.bat to run the bot."
"Restart your command prompt first!"
"MusicBot was installed to:"
"  $Install_Dir"
