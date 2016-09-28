"""Implementation of 'janitor dump' command for GDB."""

import gdb

import janitor.ansiterm
from janitor.ansiterm import term
import janitor.typecache

ENDIAN_LITTLE = 0
ENDIAN_BIG = 1

endian = None
width = None

i8086_hack = False

# Saved `dump` parameters for `stack` command
saved = False
saved_endian = None
saved_width = None

start_address = None
length = None
highlight_start = None
highlight_end = None

format_width = {
    '1': 1,
    'b': 1,
    '2': 2,
    'h': 2,
    's': 2,
    'w': 4,
    '4': 4,
    'd': 4,
    'l': 4,
    '8': 8,
    'g': 8,
    'q': 8
}

format_endian = {
    'l': ENDIAN_LITTLE,
    'b': ENDIAN_BIG
}

escapes = {
    7: '\\a',
    8: '\\b',
    9: '\\t',
    10: '\\n',
    11: '\\v',
    12: '\\f',
    13: '\\r',
    0x5c: '\\\\',
    0x22: '\\"',
    0x27: "\\'"
}

def cast_val_to_intptr(val):
    intptr_type = janitor.typecache.cache.get_intptr_type()
    if intptr_type != None:
        val = val.cast(intptr_type)
    return int(val)

def get_frame_pc(frame):
    if i8086_hack:
        return cast_val_to_intptr(frame.read_register("cs")) * 16 + frame.pc()
    return frame.pc()

def get_frame_sp(frame):
    if i8086_hack:
        return cast_val_to_intptr(frame.read_register("ss")) * 16 + cast_val_to_intptr(frame.read_register("sp"))
    return cast_val_to_intptr(frame.read_register("sp"))


def escape_string(s):
    result = []
    start = 0
    index = 0
    length = len(s)
    while index < length:
        c = ord(s[index])
        if c < 32 or c >= 127 or c == 0x5c or c == 0x22 or c == 0x27:
            if index != start:
                result.append(s[start:index])
            if c in escapes:
                result.append(escapes[c])
            else:
                hex_allowed = True
                if length > index + 1:
                    nc = s[index + 1]
                    hex_allowed = not nc.isdigit() and 'A' > nc.upper() or 'F' < nc.upper()
                if hex_allowed:
                    result.append("\\x%02x" % c)
                else:
                    result.append("\\%03o" % c)
            start = index + 1
        index += 1
    if index != start:
        result.append(s[start:])
    return "".join(result)

def remove_nonprintable(s):
    return "".join([a if 31 < ord(a) < 127 else '' for a in s])

# / is already stripped
def parse_format(fmt):
    global endian, width
    
    new_width = None
    new_endian = None
    width_letter = None
    if len(fmt) == 0:
        return
    
    for l in fmt:
        if l in format_width:
            if new_width == None:
                new_width = format_width[l]
                width_letter = l
            elif new_width == 1 or l not in format_endian:
                new_width = format_width[l]
                # Reinterpret previous 'b' as endian specifier
                pl = width_letter
                if pl in format_endian:
                    if new_endian != None and new_endian != format_endian[pl]:
                        raise gdb.GdbError ("contradictory endian specifier")
                    new_endian = format_endian[pl]
                else:
                    raise gdb.GdbError ("contradictory width specifier")
                width_letter = l
            elif l in format_endian:
                if new_endian != None and new_endian != format_endian[l]:
                    raise gdb.GdbError ("contradictory endian specifier")
                new_endian = format_endian[l]
            elif new_width != format_width[l]:
                raise gdb.GdbError ("contradictory width specifier")                
        elif l in format_endian:
            if new_endian != None and new_endian != format_endian[l]:
                raise gdb.GdbError ("contradictory endian specifier")
            new_endian = format_endian[l]
        else:
            raise gdb.GdbError ("invalid format specifier")

    if new_width != None:
        width = new_width
    
    if new_endian != None:
        endian = new_endian

class DumpBase(object):
    def __init__(self):
        pass

    def append_address(self, addr):
        # Address
        self.termline.set_color(self.ADDRESS_COLOR)
        self.termline.append("%0*X" % (self.ADDR_WIDTH, addr))
        self.termline.reset()
        self.termline.append(" ")
    

class Dump(DumpBase):
    
    ADDRESS_COLOR = term.COLOR_WHITE | term.BOLD
    BYTES_COLOR = term.COLOR_WHITE
    BYTES_SEP_COLOR = term.COLOR_WHITE
    HIGHLIGHT_BYTES_COLOR = term.COLOR_WHITE | term.BOLD
    CHARS_COLOR = term.COLOR_YELLOW | term.BOLD
    CHARS_ALT_COLOR = term.COLOR_YELLOW
    CHARS_CTRL_COLOR = term.COLOR_BLACK | term.BACKGROUND_YELLOW | term.HIGHLIGHT
    CHARS_CTRL_ALT_COLOR = term.COLOR_BLACK | term.BACKGROUND_YELLOW
    
    BYTES_PER_LINE = 16
    ALIGNED = 1
    ADDR_WIDTH = 8
    GROUPING = 8
    
    word_separator = " "
    group_separator = "-"

    def __init__(self):
        super(Dump, self).__init__()

    def append_word_start(self):
        if width > 2:
            self.termline.reset()
            self.termline.append((width-1)//2 * " ")

    def append_word_end(self, offset):
        offset += width
        if width > 1:
            self.termline.reset()
            self.termline.append((width)//2 * " ")
        if offset < self.BYTES_PER_LINE:
            self.termline.set_color(self.BYTES_SEP_COLOR)
            if offset % self.GROUPING == 0:
                self.termline.append(self.group_separator)
            else:
                self.termline.append(self.word_separator)
        return offset
        
    def append_padding(self, word_str, offset, color):
        self.append_word_start()
        if self.termline.color != color:
            self.termline.set_color(color)
        self.termline.append(word_str)
        return self.append_word_end(offset)
    
    def append_byte(self, byte_str, address):
        color = self.BYTES_COLOR
        if address != None and highlight_start != None:
            if address >= highlight_start:
                color = self.HIGHLIGHT_BYTES_COLOR
        if address != None and highlight_end != None:
            if highlight_start == None:
                color = self.HIGHLIGHT_BYTES_COLOR
            if address >= highlight_end:
                color = self.BYTES_COLOR
        if self.termline.color != color:
            self.termline.set_color(color)
        self.termline.append(byte_str)
    
    def append_bytes(self, bytes, offset, length, address):
        word_off = 0
        
        # Padding before real start
        while word_off + width <= offset:
            self.termline.reset()
            word_off = self.append_padding(width * "  ", word_off, term.DEFAULT_COLOR)
        
        # Process each n-width group of bytes
        while word_off < offset + length:
            self.append_word_start()
            word = []
            word_range = xrange(0, width, 1) if endian == ENDIAN_BIG else xrange(width - 1, -1, -1)
            for idx in word_range:
                if word_off + idx < offset or word_off + idx >= offset + length:
                    self.append_byte("  ", None)
                else:
                    self.append_byte("%02X" % ord(bytes[word_off - offset + idx]), address + word_off + idx)
            word_off = self.append_word_end(word_off)
        
        while word_off < self.BYTES_PER_LINE:
            self.termline.reset()
            word_off = self.append_padding(width * "  ", word_off, term.DEFAULT_COLOR)
        
        self.termline.reset()
        self.termline.append(" ")
    
    def append_chars(self, bytes, offset, length):
        if offset != 0:
            self.termline.append(offset * " ")
        for c in bytes:
            color = self.CHARS_COLOR
            asc = ord(c)
            
            if (asc & 127) < 32:
                color = self.CHARS_CTRL_COLOR
                asc += 64
            elif (asc & 127) == 127:
                color |= self.CHARS_CTRL_COLOR
                asc -= 64
            
            if asc > 128:
                if color == self.CHARS_CTRL_COLOR:
                    color = self.CHARS_CTRL_ALT_COLOR
                else:
                    color = self.CHARS_ALT_COLOR
                asc -= 128
            
            if color != self.termline.color:
                self.termline.set_color(color)
            
            self.termline.append(chr(asc))
    
    def to_dump_string(self, s):
        self.termline = janitor.ansiterm.TermLine()
        self.append_chars(s, 0, len(s))
        return self.termline.get_line()
    
    def invoke(self, start_addr, end_addr):
        self.termline = janitor.ansiterm.TermLine()
        
        address = start_addr

        if end_addr == None:
            height = gdb.parameter("height")
            if height != None:
                count = gdb.parameter("height") / 2 - 2
            else:
                count = 12
            end_addr = start_addr + count * self.BYTES_PER_LINE - 1
            
        if self.ALIGNED > 1:
            address -= address % self.ALIGNED
        
        while address <= end_addr:
            self.termline.start()
            
            # Address
            self.append_address(address)

            # Number of bytes to read
            start_off = 0
            if address < start_addr:
                start_off = start_addr - address
            bytes_to_read = self.BYTES_PER_LINE - start_off
            if address + bytes_to_read > end_addr:
                bytes_to_read = end_addr - address + 1
            
            bytes = gdb.selected_inferior().read_memory(address + start_off, bytes_to_read)

            # Bytes
            self.append_bytes(bytes, start_off, bytes_to_read, address)
            
            # Chars
            self.append_chars(bytes, start_off, bytes_to_read)
            
            print self.termline.get_line()
            
            address += self.BYTES_PER_LINE
    
        return end_addr + 1

dump_obj = Dump()

def dump(start_addr, end_addr):
    return dump_obj.invoke(start_addr, end_addr)
