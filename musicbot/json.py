import json
import logging

log = logging.getLogger(__name__)

class Json:
    def __init__(self, json_file):
        log.debug('Init JSON obj with {0}'.format(json_file))
        self.file = json_file
        self.data = self.parse()

    def parse(self):
        """Parse the file as JSON"""
        with open(self.file, encoding='utf-8') as data:
            try:
                parsed = json.load(data)
            except Exception:
                log.error('Error parsing {0} as JSON'.format(self.file), exc_info=True)
        return parsed

    def get(self, item, fallback=None):
        """Gets an item from a JSON file"""
        try:
            data = self.data[item]
        except KeyError:
            log.warning('Could not grab data from i18n key {0}.'.format(item, fallback))
            data = fallback
        return data
