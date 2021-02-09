# NSSM

This guide will assist you in installing NSSM to run Musicbot in the background of Windows, automatically restart it if it crashes, and at startup.

1. Download the latest release of [NSSM](https://nssm.cc/release/nssm-2.24.zip).
2. Extract the zip somewhere easily accessible.
3. Open a command prompt as administrator
4. cd to the Win64 folder within the `nssm-2.24` folder you extracted from the zip file.
5. Run `where python`. You'll need this information while setting up the Musicbot service.
6. Run `.\nssm.exe install`
7. In the Path field, you'll want to use the output of `where python` from earlier.
8. In the Starting Directory field, you'll want to use the MusicBot folder you got from installing Musicbot.
9. In the Arguments field, just put `run.py`
10. Set the Service Name field to MusicBot, or something you'll remember, and hit Install Service.
11. Run `.\nssm.exe start MusicBot`

There you have it, Musicbot should now be running in the background, should restart whenever it crashes, and should start on startup.
