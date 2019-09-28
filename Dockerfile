FROM archlinux/base
LABEL maintainer="Winding"

#pkg
RUN pacman -Sy --noconfirm git python ffmpeg opus libsodium git \
\
#pip_dep
&& pip install --upgrade pip \
&& pip install --no-cache-dir -r requirements.txt \
\
&& git clone https://github.com/Winding6636/DiscoMusicBot_py.git /usr/src/musicbot

WORKDIR /usr/src/musicbot
VOLUME /usr/src/musicbot/config
ADD config /usr/src/musicbot/config

ENV APP_ENV=docker
ENTRYPOINT ["python", "dockerentry.py"]
