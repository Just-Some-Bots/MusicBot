"""rope, a python refactoring library"""

from pkg_resources import get_distribution


INFO = __doc__
VERSION = get_distribution("rope").version
COPYRIGHT = """\
Copyright (C) 2021-2022 Lie Ryan
Copyright (C) 2019-2021 Matej Cepl
Copyright (C) 2015-2018 Nicholas Smith
Copyright (C) 2014-2015 Matej Cepl
Copyright (C) 2006-2012 Ali Gholami Rudi
Copyright (C) 2009-2012 Anton Gritsay

This program is free software: you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation, either
version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this program.  If not, see
<https://www.gnu.org/licenses/>."""
