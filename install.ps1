# This script is designed to be used without pulling the repository first!
# You can simply download and run it to have MusicBot installed for you.
# Current the script only supports one installation per user account.
#
# Notice:
#  If you want to run this .ps1 script without setting execution policy in PowerShell,
#  you can make use of the following command in command-prompt.
#
#    powershell.exe -noprofile -executionpolicy bypass -file install.ps1
#
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

$iagree = Read-Host "Would you like to continue with the install? [y/n]"
if($iagree -ne "Y" -and $iagree -ne "y")
{
    # exit early if the user does not want to continue.
    Return
}

if (-Not (Get-Command winget -ErrorAction SilentlyContinue) )
{
    ""
    "Sorry, you must install WinGet to use this installer."
    "Supposedly included with Windows, but we couldn't find it."
    "You can get it via Microsoft Store, the Official repo on github, or "
    "use the following link to quickly download an installer for it:"
    "  https://aka.ms/getwinget  "
    ""
    Return
}

# -----------------------------------------------------CONSTANTS-------------------------------------------------------

$DEFAULT_URL_BASE = "https://discordapp.com/api"

# ----------------------------------------------INSTALLING DEPENDENCIES------------------------------------------------

# Check if git is installed
"Checking if git is already installed..."
Invoke-Expression "winget list -q Git.Git" | Out-Null
if (!($LastExitCode -eq 0))
{
    # install git
    "Installing git..."
    Invoke-Expression "winget install Git.Git"
    "Done."
}
else
{
    "Git already installed."
}
""

# Check if Any python 3 is installed
"Checking if python is already installed..."
Invoke-Expression "winget list -q Python.Python.3" | Out-Null
if (!($LastExitCode -eq 0))
{
    # install python version 3.11 with the py.exe launcher.
    "Installing python..."
    Invoke-Expression "winget install Python.Python.3.11 --custom \`"/passive Include_launcher=1\`""
    "Done."
}
else
{
    "Python already installed."
}
""

# Check if ffmpeg is installed
"Checking if FFmpeg is already installed..."
Invoke-Expression "winget list -q Gyan.FFmpeg" | Out-Null
if (!($LastExitCode -eq 0))
{
    # install FFmpeg
    "Installing FFmpeg..."
    Invoke-Expression "winget install Gyan.FFmpeg"
    "Done."
}
else
{
    "FFmpeg already installed."
}
""

# NOTE: if we need to refresh the environment vars (Path, etc.) after installing
# the above packages, we may need to add some other dependency which provides
# RefreshEnv.bat or manually manage paths to newly installed exes.
# Users should be able to get around this by restarting the powershell script.

# --------------------------------------------------PULLING THE BOT----------------------------------------------------

# Test if we need to pull the bot or not by checking for some files.
$MB_Reqs_File=(pwd).Path + '\requirements.txt'
$MB_Module_Dir=(pwd).Path + '\musicbot'
$MB_Git_Dir=(pwd).Path + '\.git'

if((Test-Path $MB_Reqs_File) -and (Test-Path $MB_Module_Dir) -and (Test-Path $MB_Git_Dir) ) {
    ""
    "Installer detected an existing clone, and will continue installing with the current source."
    ""
} else {
    ""
    "MusicBot currently has three branches available."
    "  master - An older MusicBot, for older discord.py. May not work without tweaks!"
    "  review - Newer MusicBot, usually stable with less updates than the dev branch."
    "  dev    - The newest MusicBot, latest features and changes which may need testing."
    ""
    $experimental = Read-Host "Enter the branch name you want to install"
    if($experimental -eq "dev")
    {
        "Installing dev branch..."
        $branch = "dev"
    }
    if($experimental -eq "review")
    {
        "Installing review branch..."
        $branch = "review"
    }
    else
    {
        "Installing master branch..."
        $branch = "master"
    }

    Invoke-Expression "git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b $branch"
    Invoke-Expression "cd MusicBot"
    ""
}

# --------------------------------------------INSTALL PYTHON DEPENDENCIES----------------------------------------------

if (Get-Command "python" -errorAction SilentlyContinue)
{
    Invoke-Expression "python -c 'import sys; exit(0 if sys.version_info >= (3, 8) else 1)'" | Out-Null
    if($LastExitCode -eq 0)
    {
        $PYTHON = "python"
    }
}

$versionArray = "3.8", "3.9", "3.10", "3.11", "3.12"

foreach ($version in $versionArray)
{
    Invoke-Expression "py -$version -c 'exit()'" 2>$null
    if($LastExitCode -eq 0)
    {
        $PYTHON = "py -$version"
    }
}

"Using $PYTHON to install and run MusicBot..."
Invoke-Expression "$PYTHON -m pip install --upgrade -r requirements.txt" 

# -------------------------------------------------CONFIGURE THE BOT---------------------------------------------------
""
"MusicBot is almost ready to run, we just need to configure the bot."
"This installer provides an automated, but minimal, guided configuration."
"It will ask you to enter a bot token."
""
$iagree = Read-Host "Would you like to continue with configuration? [y/n]"
if($iagree -ne "Y" -and $iagree -ne "y")
{
    "All done!"
    "Remember to configure your bot token and other options before you start."
    "You can use run.bat to start the MusicBot."
    Return
}


Copy-Item ".\config\example_options.ini" -Destination ".\config\options.ini"

# GET AND VERIFY TOKEN
""
"Please enter your bot token. This can be found in your discordapp developer page." 
$token = Read-Host "Enter Token" -AsSecureString
$token_plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($token))
$header = @{
    "Authorization" = "Bot $token_plain"
    "Content-Type" = "application/json"
}
$result = Invoke-WebRequest -Headers $header -Method "GET" -Uri "$DEFAULT_URL_BASE/users/@me"
$result_code = $result.StatusCode
$result_content = $result.Content
if (!($result_code -eq 200))
{
    "Error getting user profile, is the token correct? ($result_code $result_content)"
    ""
    "You can finish the configuration manually by editing the options.ini file in the config folder."
    Return
}
$result_object = ConvertFrom-Json -InputObject $result_content
# Cause whoever wrote ConvertFrom-Json cmdlet was insane and use some strange data type instead
$result_table = @{}
$result_object.PsObject.Properties | ForEach-Object{
    $result_table[$_.Name] = $_.Value
}
$result_table += @{"token" = $token_plain}
$config = (Get-Content -Path ".\config\options.ini") -creplace "bot_token", $token_plain

# GET PREFIX
$cprefix = Read-Host "Would you like to change the command prefix? [N/y]: "
if($cprefix -eq "Y" -or $cprefix -eq "y")
{
    "Please enter the prefix you'd like for your bot."
    $prefix = Read-Host "This is what comes before all commands. The default is [!] "
    $config = $config -creplace "CommandPrefix = !", "CommandPrefix = $prefix"
}
else
{
    "Using default prefix [!]"
}

# GET OWNER
$cowner = Read-Host "Would you like to automatically get the owner ID from the OAuth application? [Y/n]: "
if($cowner -eq "N" -or $cowner -eq "n")
{
    $owner = Read-Host "Please enter the owner ID. "
    $config = $config -creplace "OwnerID = auto", "OwnerID = $owner"
}
else
{
    "Getting owner ID from OAuth application..."
}

# GET AP
$cap = Read-Host "Would you like to enable the autoplaylist? [Y/n] "
if($cap -eq "N" -or $cap -eq "n")
{
    $config = $config -creplace "UseAutoPlaylist = yes", "UseAutoPlaylist = no"
    "Autoplaylist disabled"
}
else
{
    "Autoplaylist enabled"
}

"Saving your config..."
Set-Content -Path ".\config\options.ini" -Value $config

"You can now use run.bat to run the bot"
