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
    if([int](Invoke-Expression "python -c 'import sys; version=sys.version_info[:3]; print(\`"{0}\`".format(version[2]))'") -gt 2 -and [int]$pythonver[1] -gt 4)
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
Copy-Item ".\config\example_options.ini" -Destination ".\config\options.ini"

# Still too lazy to do the rest
"Configure the bot by following this guide: https://just-some-bots.github.io/MusicBot/using/configuration/"
"Then use run.bat to run the bot"