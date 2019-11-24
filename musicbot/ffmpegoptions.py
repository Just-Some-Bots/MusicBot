import re

from .utils import get_command, run_command

async def get_equalize_option(filename, log):
    log.debug('Calculating mean volume of {0}'.format(filename))
    cmd = '"' + get_command('ffmpeg') + '" -i "' + filename + '" -af loudnorm=I=-24.0:LRA=7.0:TP=-2.0:linear=true:print_format=json -f null /dev/null'
    output = await run_command(cmd, log)
    output = output.decode("utf-8")
    log.debug(output)
    # print('----', output)

    I_matches = re.findall(r'"input_i" : "([-]?([0-9]*\.[0-9]+))",', output)
    if (I_matches):
        log.debug('I_matches={}'.format(I_matches[0][0]))
        I = float(I_matches[0][0])
    else:
        log.debug('Could not parse I in normalise json.')
        I = float(0)

    LRA_matches = re.findall(r'"input_lra" : "([-]?([0-9]*\.[0-9]+))",', output)
    if (LRA_matches):
        log.debug('LRA_matches={}'.format(LRA_matches[0][0]))
        LRA = float(LRA_matches[0][0])
    else:
        log.debug('Could not parse LRA in normalise json.')
        LRA = float(0)

    TP_matches = re.findall(r'"input_tp" : "([-]?([0-9]*\.[0-9]+))",', output)
    if (TP_matches):
        log.debug('TP_matches={}'.format(TP_matches[0][0]))
        TP = float(TP_matches[0][0])
    else:
        log.debug('Could not parse TP in normalise json.')
        TP = float(0)

    thresh_matches = re.findall(r'"input_thresh" : "([-]?([0-9]*\.[0-9]+))",', output)
    if (thresh_matches):
        log.debug('thresh_matches={}'.format(thresh_matches[0][0]))
        thresh = float(thresh_matches[0][0])
    else:
        log.debug('Could not parse thresh in normalise json.')
        thresh = float(0)

    offset_matches = re.findall(r'"target_offset" : "([-]?([0-9]*\.[0-9]+))', output)
    if (offset_matches):
        log.debug('offset_matches={}'.format(offset_matches[0][0]))
        offset = float(offset_matches[0][0])
    else:
        log.debug('Could not parse offset in normalise json.')
        offset = float(0)

    return ' -af loudnorm=I=-24.0:LRA=7.0:TP=-2.0:linear=true:measured_I={}:measured_LRA={}:measured_TP={}:measured_thresh={}:offset={}'.format(I, LRA, TP, thresh, offset)