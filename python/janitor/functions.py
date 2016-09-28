"""These functions are not integral part of janitor package they are just helper functions use bye me."""

import gdb

import janitor.typecache

class FarFunction(gdb.Function):
    def __init__(self):
         super (FarFunction, self).__init__("far")
    
    def invoke(self, seg, off):
        intptr_type = janitor.typecache.cache.get_intptr_type()
        if intptr_type != None:
            off = off.cast(intptr_type)
            seg = seg.cast(intptr_type)
        return int(seg) * 16 + int(off)

FarFunction()
