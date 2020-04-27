#!/bin/sh

if [[ ! -f "/musicbot/config/example_options.ini" ]]; then
    cp -r /musicbot/sample_config/* /musicbot/config
fi

python3 run.py $@