This walkthrough will take you through the steps required to host the bot externally using a VPS. For this, we recommend the use of Amazon Web Service. You must first have a Personal Account with them before continuing with this walkthrough.

## AWS Installation

Before you can run a program through AWS, you must first create an EC2 Instance. To do this, Navigate to the “Services” tab in the top left and select EC2.

[![](https://aleanaazure.xyz/lib/exe/fetch.php?w=512&h=512&tok=887f2d&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FSelect_EC2.PNG)](https://aleanaazure.xyz/lib/exe/fetch.php?tok=a8e437&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FSelect_EC2.PNG "https://britishbenji.github.io/MusicBot/images/AWS/Select_EC2.PNG")

From here, you can click the Orange “Launch Instance” button, to start setting up your instance.

[![](https://aleanaazure.xyz/lib/exe/fetch.php?w=512&h=512&tok=6d2992&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FLaunch_Instance.PNG)](https://aleanaazure.xyz/lib/exe/fetch.php?tok=fa29ee&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FLaunch_Instance.PNG "https://britishbenji.github.io/MusicBot/images/AWS/Launch_Instance.PNG")

You will be given many different options for which option to run. Our suggestion is that you choose the “Ubuntu Server 18.04 LTS (HMV)” service and this walkthrough will be catered to that option.

[![](https://aleanaazure.xyz/lib/exe/fetch.php?w=512&h=512&tok=52beda&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FFree_Tier_Ubuntu.PNG)](https://aleanaazure.xyz/lib/exe/fetch.php?tok=bd0c9e&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FFree_Tier_Ubuntu.PNG "https://britishbenji.github.io/MusicBot/images/AWS/Free_Tier_Ubuntu.PNG")

From here, click “Review and Launch”, then “Launch” your instance. You will receive a pop-up, asking you to “Select an existing key pair or create a new key pair.”
Here, you will need to select “Create a new key pair” from the drop-down box, and give it a name.
Then download your key, and click “Launch Instances.”
Note: It is suggested that you save this key in multiple places to prevent it being lost, as once you Launch your instance, there is no way to recover the key without creating a brand new Instance.

[![](https://aleanaazure.xyz/lib/exe/fetch.php?w=512&h=512&tok=66b704&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FCreate_New_Key_Pair.PNG)](https://aleanaazure.xyz/lib/exe/fetch.php?tok=489525&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FCreate_New_Key_Pair.PNG "https://britishbenji.github.io/MusicBot/images/AWS/Create_New_Key_Pair.PNG")

---

## Instance Interaction

Now that you have set up your Instance with AWS, we need to find a way to interact with it.
This can be done with any form of SSH client, however, for this example, we’ll be using PuTTY (which can be downloaded and installed from [here](https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html "https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html"))

With PuTTY installed, we first need to open PuTTYgen, this will allow use to change the Priavte Key Amazon provided us with into something PuTTY can interact with and use.
With the PuTTYgen program open, load an existing private key file using the “Load” button, and save it as a Public Key.
To keep things simple, save this with the same filename as your original key, with the .ppk file extension.

[![](https://aleanaazure.xyz/lib/exe/fetch.php?w=512&h=512&tok=df744d&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FPuTTYgen_UI.PNG)](https://aleanaazure.xyz/lib/exe/fetch.php?tok=673278&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FPuTTYgen_UI.PNG "https://britishbenji.github.io/MusicBot/images/AWS/PuTTYgen_UI.PNG")

Once you have saved this, open PuTTY and AWS side by side. On your AWS window, find and copy your “Public DNS (IPv4)”, and paste this into the “Host Name (or IP address)” text box with the prefix “ubuntu@”

[![](https://aleanaazure.xyz/lib/exe/fetch.php?w=512&h=512&tok=bcffa4&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FConnect_IP.PNG)](https://aleanaazure.xyz/lib/exe/fetch.php?tok=907d59&media=https%3A%2F%2Fbritishbenji.github.io%2FMusicBot%2Fimages%2FAWS%2FConnect_IP.PNG "https://britishbenji.github.io/MusicBot/images/AWS/Connect_IP.PNG")

Following on from this page, expand the “SSH” tab on the right hand side of the screen and click “Auth” Select your .ppk file using the “Browse…” option, then go back to the “Session” tab and click open.
You will be brought to a black screen with text on it, you are now in your Ubuntu Workspace on your EC2 Instance.
From here, you can install the bot by following the [configure]({{ site.baseurl }}/installing/ubuntu.md) guide, and can keep it running in the background using [PM2]({{ site.baseurl }}/installing/pm2.md).
