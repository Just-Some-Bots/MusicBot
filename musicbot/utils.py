import json
from slugify import slugify


def load_file(filename):
    try:
        with open(filename) as f:
            results = []
            for line in f:
                line = line.strip()
                if line:
                    if not line.startswith('#'):
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


def load_json(filename):
    try:
        with open(filename, encoding='utf-8') as f:
            return json.loads(f.read())

    except IOError as e:
        print("Error loading", filename, e)
        return []


def write_json(filename, contents):
    with open(filename, 'w') as outfile:
        outfile.write(json.dumps(contents, indent=2))


def do_slugify(value):
    return slugify(value, separator='_')
