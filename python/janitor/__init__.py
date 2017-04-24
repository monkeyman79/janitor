"""Collection on GDB commands useful for low-level debugging, aimed at bringing debug.exe flavor into GDB command line interface.
"""

import sys
import gdb

if sys.version_info < (3,0,0):
    gdb.write("Warning: Janitor expects Python version >= 3.0.0\n");

gdb_version = gdb.VERSION.split('.')
if int(gdb_version[0]) < 7 or (int(gdb_version[0]) == 7 and int(gdb_version[1]) < 12):
    gdb.write("Warning: Janitor expects GDB version >= 7.12\n");

