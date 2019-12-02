import os

modules = list()

for module in os.listdir(os.path.dirname(__file__)):
    if module == '__init__.py' or module[-3:] != '.py':
        continue
    modules.append('default.{}'.format(module[:-3]))

del module
