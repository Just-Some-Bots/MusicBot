import re
import decimal
import unicodedata

_USER_ID_MATCH = re.compile(r'<@(\d+)>')


def load_file(filename, skip_commented_lines=True, comment_char='#'):
    try:
        with open(filename) as f:
            results = []
            for line in f:
                line = line.strip()

                if line and not (skip_commented_lines and line.startswith(comment_char)):
                    results.append(line)

            return results

    except IOError as e:
        print("Error loading", filename, e)
        return []


def write_file(filename, contents):
    with open(filename, 'w') as f:
        for item in contents:
            f.write(str(item))
            f.write('\n')


def extract_user_id(argument):
    match = _USER_ID_MATCH.match(argument)
    if match:
        return int(match.group(1))


def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


def sane_round_int(x):
    return int(decimal.Decimal(x).quantize(1, rounding=decimal.ROUND_HALF_UP))
