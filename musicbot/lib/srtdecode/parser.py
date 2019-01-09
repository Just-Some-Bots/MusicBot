import logging

from .exceptions import SRTParseError

log = logging.getLogger(__name__)

# This is basically writing a parser of a LR(1) compiler

class Timestamp:
    def __init__(self, hour: int, minute: int, second: int, millisecond: int):
        self.hour = hour
        self.minute = minute
        self.second = second
        self.millisecond = millisecond

    def __str__(self):
        return '{}:{}:{},{}'.format(self.hour, self.minute, self.second, self. millisecond)

    def to_millisecond(self):
        return (((self.hour*60)+self.minute)*60+self.second)*1000+self.millisecond

class SRTBlock:
    def __init__(self, block_num: int, time_start: Timestamp, time_end: Timestamp, text_list):
        self.block_num = block_num
        self.time_start = time_start
        self.time_end = time_end
        self.text_list = text_list

    def __str__(self):
        return '{}\n{} --> {}\n{}'.format(self.block_num, self.time_start, self.time_end, self. text_list)

class Reader:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    @property
    def current(self):
        if self.pos == len(self.text):
            return None
        return self.text[self.pos]

    def advance(self):
        self.pos += 1

    def eat(self, text):
        if self.text[self.pos:self.pos+len(text)] == text:
            self.pos += len(text)
        else:
            raise SRTParseError('Error eating text at pos {}: {}'.format(self.pos ,text))

def gen_srt_block_list_from_file(f):
    '''
    grammar:
    SRTBlockList: SRTBlock*\n
    as            block*\n
    after_p       block_list = get_all(block)
    SRTBlock: INT\nTIME --> TIME\n(STRL)*\n
    as        block_num\ntime_start --> time_end\n(text)*\n
    after_p   text_list = get_all(text)
    TIME: INT{2}:INT{2}:INT{2},INT{3}
    '''
    
    def get_int(buf: Reader, n: int = None):
        ret = 0
        if buf.current:
            while buf.current and buf.current.isdigit() and (not n or n > 0):
                ret *= 10
                ret += int(buf.current)
                buf.advance()
                if n:
                    n -= 1
            return ret
        else:
            raise EOFError('Reach the end of buffer')

    def get_strl(buf: Reader):
        ret = []
        if buf.current:
            while buf.current and buf.current != '\n':
                ret.append(buf.current)
                buf.advance()
            if buf.current:
                buf.advance()
            return ''.join(ret)
        else:
            raise EOFError('Reach the end of buffer')

    def get_time(buf: Reader):
        hour = get_int(buf, 2)
        buf.eat(':')
        minute = get_int(buf, 2)
        if 59 < minute:
            raise SRTParseError('Error parsing srt timestamp, minute is larger than 60')
        buf.eat(':')
        second = get_int(buf, 2)
        if 59 < second:
            raise SRTParseError('Error parsing srt timestamp, second is larger than 60')
        buf.eat(',')
        millisecond = get_int(buf, 3)
        return Timestamp(hour, minute, second, millisecond)

    def get_srtblock(buf: Reader):
        block_num = get_int(buf)
        buf.eat('\n')
        time_start = get_time(buf)
        buf.eat(' --> ')
        time_end= get_time(buf)
        buf.eat('\n')
        text_list = []
        while buf.current and buf.current != '\n':
            text_list.append(get_strl(buf))
        buf.eat('\n')
        return SRTBlock(block_num, time_start, time_end, text_list)

    def get_srtblocklist(buf: Reader):
        block_list = []
        while buf.current and buf.current != '\n':
            block_list.append(get_srtblock(buf))
        # buf.eat('\n')
        return block_list

    buffer = Reader(f.read())
    return get_srtblocklist(buffer)

def is_sorted(l, key = lambda x, y: x < y): 
    for i, el in enumerate(l[1:]):
        if not key(l[i], el):
            return False
    return True

def get_transcript(block_list, time_sep: int = 4):
    assert is_sorted(block_list, lambda x, y: x.block_num < y.block_num)
    if len(block_list) == 0:
        return []
    ret = block_list[0].text_list.copy()
    ltime = block_list[0].time_end.to_millisecond()
    for i, el in enumerate(block_list[1:]):
        # log.debug((block_list[i].time_end.to_millisecond() + time_sep*1000 , el.time_start.to_millisecond()))
        if block_list[i].time_end.to_millisecond() + time_sep*1000 < el.time_start.to_millisecond():
            ret.append('')
            ret += el.text_list
            ltime = el.time_end.to_millisecond()
        else:
            if set(block_list[i].text_list) == set(el.text_list):
                # @TheerapakG: hopefully won't break
                ret += el.text_list
                ltime = el.time_end.to_millisecond()

            else:
                # @TheerapakG: probably a terrible bad sub fix
                for t in el.text_list:
                    if t not in block_list[i].text_list:
                        if ltime + time_sep*1000 < el.time_start.to_millisecond():
                            ret.append('')
                        ret.append(t)
                        ltime = el.time_end.to_millisecond()
    return ret