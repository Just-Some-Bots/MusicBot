import os
from importlib import import_module

cogs = list()

for module in os.listdir(os.path.dirname(__file__)):
    if module == '__init__.py' or module[-3:] != '.py':
        continue
    _module = import_module('.{}'.format(module[:-3]), __name__)
    cogs.extend(_module.cogs)

del module
del _module
