
import gdb

class TypeCache(object):
    def __init__(self):
        self.cache = {}
        self.intptr_type = False
    
    def clear(self):
        self.cache = {}
        self.intptr_type = False
    
    def get_type(self, typename):
        if typename in self.cache:
            return self.cache[typename]
        
        try:
            gdb_type = gdb.lookup_type(typename)
            self.cache[typename] = gdb_type
            return gdb_type
        except:
            pass
        
        try:
            proto = gdb.parse_and_eval("(%s*)0" % typename)
            gdb_type = proto.type.target()
            self.cache[typename] = gdb_type
            return gdb_type
        except:
            pass
        
        return None
    
    def get_intptr_type(self):
        if self.intptr_type != False:
            return self.intptr_type
        ptr_type = self.get_type("void*")
        if ptr_type == None:
            self.intptr_type = None
            return None
        ulong_type = self.get_type("unsigned long")
        if ulong_type == None:
            self.intptr_type = None
            return None
        if ulong_type.sizeof >= ptr_type.sizeof:
            self.intptr_type = ulong_type
            return ulong_type
        ullong_type = self.get_type("unsigned long long")
        self.intptr_type = ullong_type
        return ullong_type
    
cache = TypeCache()
