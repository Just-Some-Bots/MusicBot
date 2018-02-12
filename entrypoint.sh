#!/usr/bin/env bash
export OPTIONS=config/options.ini

if [ ! -f $OPTIONS ]; then
  cp config/example_options.ini $OPTIONS;
fi

if [ ! -z $BOTTOKEN ]; then
  sed -i 's/Token = bot_token/Token = '"$BOTTOKEN"'/' $OPTIONS
fi

if [ ! -z $BINDTOCHANNELS ]; then
  sed -i 's/;BindToChannels =/BindToChannels = '"$BINDTOCHANNELS"'/' $OPTIONS
fi

if [ ! -z $AUTOJOINCHANNELS ]; then
  sed -i 's/AutojoinChannels; =/AutojoinChannels = '"$AUTOJOINCHANNELS"'/' $OPTIONS
fi

if [ ! -z $SAVEVIDEOS ]; then
  sed -i 's/SaveVideos = yes/SaveVideos = '"$SAVEVIDEOS"'/' $OPTIONS
fi

cat << EOF > config/permissions.ini
[Default]
CommandWhitelist = play perms queue np skip search id help clean
; CommandBlacklist =
IgnoreNonVoice = play skip search
MaxSongLength = 1200
MaxSongs = 0
AllowPlaylists = yes
; MaxPlaylistLength = 20
InstaSkip = no
[DJ]
CommandBlacklist = blacklist listids
GrantToRoles = $DJROLES
; UserList =
MaxSongLength = 0
MaxSongs = 0
MaxPlaylistLength = 0
AllowPlaylists = yes
InstaSkip = yes
EOF

exec python3.5 run.py
