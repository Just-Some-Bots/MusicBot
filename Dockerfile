FROM alpine:3.4

# Install Dependencies
RUN apk update \
 && apk add python3-dev ca-certificates gcc make linux-headers musl-dev ffmpeg libffi-dev bash

# Add project source
COPY . /usr/src/MusicBot
WORKDIR /usr/src/MusicBot

# Install pip dependencies
RUN pip3 install -r requirements.txt
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
