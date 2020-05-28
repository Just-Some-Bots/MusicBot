# Check if running as administrator
if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
{
    # Run as administrator
    if (Test-Path "$PSHome\powershell.exe")
    {
        # Normal Powershell
        Start-Process -FilePath "$PSHome\powershell.exe" -Verb RunAs "-NoProfile -ExecutionPolicy Bypass -Command `"cd '$pwd'; & '$PSCommandPath';`"";
    }
    if (Test-Path "$PSHome\pwsh.exe")
    {
        # Powershell 6
        Start-Process -FilePath "$PSHome\pwsh.exe" -Verb RunAs "-NoProfile -ExecutionPolicy Bypass -Command `"cd '$pwd'; & '$PSCommandPath';`"";
    }

}

# -----------------------------------------------------CONSTANTS-------------------------------------------------------

$DEFAULT_URL_BASE = "https://discordapp.com/api"

# ----------------------------------------------INSTALLING DEPENDENCIES------------------------------------------------

# We will be using chocolatey to aid our installation
# Check if chocolatey is installed
"checking if chocolatey is already installed..."
if (!(Get-Command "choco" -errorAction SilentlyContinue))
{
    # install chocolatey
    "installing chocolatey..."
    Set-ExecutionPolicy Bypass -Scope Process -Force;
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072;
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'));
}
else
{
    "chocolatey already installed"
}

# Check if git is installed
"checking if git is already installed..."
if (!(Get-Command "git" -errorAction SilentlyContinue))
{
    # install git
    "installing git..."
    Invoke-Expression "choco install git -y --params '`"/GitOnlyOnPath`"'"
}
else
{
    "git already installed"
}

# Check if python is installed
"checking if python is already installed..."
if (!((Get-Command "python" -errorAction SilentlyContinue) -or (Get-Command "py" -errorAction SilentlyContinue)))
{
    # install python (chocolatey does not allow specifying version range currently so it's going to be pegged like this atm)
    "installing python..."
    Invoke-Expression "choco install python3 -y --version=3.8.2"
}
else
{
    "python already installed"
}

Invoke-Expression "refreshenv"

# --------------------------------------------------PULLING THE BOT----------------------------------------------------

"Do you want to install experimental branch?"
$experimental = Read-Host "Installing experimental branch means limited support, but you get access to newer fixes and features. (N/y): "
if($experimental -eq "Y" -or $experimental -eq "y")
{
    "There currently are two experimental branch of the bot: review and cogs-rewrite"
    ""
    "The review branch might contains fixes to the master branch or some new features"
    "The cogs-rewrite branch is a rewritten version of the bot and contain several new features"
    "compared to the master and the review branch, but can be very unstable"
    ""
    $review = Read-Host "Do you want to install the review branch or the cogs-rewrite branch? ([r]eview/[c]ogs-rewrite): "
    if($review -eq "C" -or $review -eq "C" -or $review -eq "cogs-rewrite" -or $review -eq "Cogs-rewrite")
    {
        "installing cogs-rewrite branch..."
        $branch = "cogs-rewrite"
    }
    else
    {
        "installing review branch..."
        $branch = "review"
    }
}
else
{
    "installing master branch..."
    $branch = "master"
}

Invoke-Expression "git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b $branch"
Invoke-Expression "cd MusicBot"

# --------------------------------------------INSTALL PYTHON DEPENDENCIES----------------------------------------------

if (Get-Command "python" -errorAction SilentlyContinue)
{
    $pythonver = @()
    $pythonver += Invoke-Expression "python -c 'import sys; version=sys.version_info[:3]; print(\`"{0}\`".format(version[0]))'"
    $pythonver += Invoke-Expression "python -c 'import sys; version=sys.version_info[:3]; print(\`"{0}\`".format(version[1]))'"
    $pythonver += Invoke-Expression "python -c 'import sys; version=sys.version_info[:3]; print(\`"{0}\`".format(version[2]))'"
    if([int]($pythonver[0]) -gt 2 -and [int]($pythonver[1]) -gt 4)
    {
        if([int]($pythonver[1]) -eq 5 -and [int]($pythonver[2]) -gt 3)
        {
            $PYTHON = "python"
        }
    }
}

Invoke-Expression "py -3.5 -c 'exit()'"
if($LastExitCode -eq 0)
{
    if([int](Invoke-Expression "python -c 'import sys; version=sys.version_info[:3]; print(\`"{0}\`".format(version[2]))'") -gt 2)
    {
        $PYTHON = "py -3.5"
    }
}
Invoke-Expression "py -3.6 -c 'exit()'"
if($LastExitCode -eq 0)
{
    $PYTHON = "py -3.6"
}
Invoke-Expression "py -3.7 -c 'exit()'"
if($LastExitCode -eq 0)
{
    $PYTHON = "py -3.7"
}
Invoke-Expression "py -3.8 -c 'exit()'"
if($LastExitCode -eq 0)
{
    $PYTHON = "py -3.8"
}

Invoke-Expression "$PYTHON -m pip install --upgrade -r requirements.txt"

# -------------------------------------------------CONFIGURE THE BOT---------------------------------------------------
Copy-Item ".\config\example_options.ini" -Destination ".\config\options.ini"

# GET AND VERIFY TOKEN
""
"Please enter your bot token. This can be found in your discordapp developer page." 
$token = Read-Host "Enter Token:" -AsSecureString
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