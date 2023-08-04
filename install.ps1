# -----------------------------------------------------CONSTANTS-------------------------------------------------------

$DEFAULT_URL_BASE = "https://discordapp.com/api"

# ----------------------------------------------INSTALLING DEPENDENCIES------------------------------------------------

# Check if git is installed
"checking if git is already installed..."
Invoke-Expression "winget list -q Git.Git"
if (!($LastExitCode -eq 0))
{
    # install git
    "installing git..."
    Invoke-Expression "winget install Git.Git"
}
else
{
    "git already installed"
}

# Check if python is installed
"checking if python is already installed..."
Invoke-Expression "winget list -q Python.Python.3"
if (!($LastExitCode -eq 0))
{
    # install python
    "installing python..."
    Invoke-Expression "winget install Python.Python.3.11 --custom \`"/passive Include_launcher=1\`""
}
else
{
    "python already installed"
}

Invoke-Expression "refreshenv"

# --------------------------------------------------PULLING THE BOT----------------------------------------------------

"Do you want to install experimental (review) branch?"
$experimental = Read-Host "Installing experimental (review) branch means limited support, but you get access to newer fixes and features. (N/y): "
if($experimental -eq "Y" -or $experimental -eq "y")
{
    "installing review branch..."
    $branch = "review"
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
    Invoke-Expression "python -c 'import sys; exit(0 if sys.version_info >= (3, 6) else 1)'"
    if($LastExitCode -eq 0)
    {
        $PYTHON = "python"
    }
}

$versionArray = "3.6", "3.7", "3.8", "3.9", "3.10", "3.11"

foreach ($version in $versionArray)
{
    Invoke-Expression "py -$version -c 'exit()'"
    if($LastExitCode -eq 0)
    {
        $PYTHON = "py -$version"
    }
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
