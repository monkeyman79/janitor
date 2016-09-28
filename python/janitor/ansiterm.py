
class Term(object):
    """Collections of constants and setting for ANSI terminal sequence generation."""
    
    # Those are real ANSI color number, used as foreground color codes
    COLOR_BLACK = 0
    COLOR_RED = 1
    COLOR_GREEN = 2
    COLOR_YELLOW = 3
    COLOR_BLUE = 4
    COLOR_MAGENTA = 5
    COLOR_CYAN = 6
    COLOR_WHITE = 7
    FG_MASK = 7
    
    # Internal codes for extended attributes
    ATTR_SHIFT = 3
    BOLD = 8
    HIGHLIGHT = 16
    INVERSE = 32
    ATTR_MASK = BOLD | HIGHLIGHT | INVERSE
    
    # Assign couple of bits for background colors
    BG_SHIFT = 8
    BACKGROUND_BLACK = 0
    BACKGROUND_RED = COLOR_RED << BG_SHIFT
    BACKGROUND_GREEN = COLOR_GREEN << BG_SHIFT
    BACKGROUND_YELLOW = COLOR_YELLOW << BG_SHIFT
    BACKGROUND_BLUE = COLOR_BLUE << BG_SHIFT
    BACKGROUND_MAGENTA = COLOR_MAGENTA << BG_SHIFT
    BACKGROUND_CYAN = COLOR_CYAN << BG_SHIFT
    BACKGROUND_WHITE = COLOR_WHITE << BG_SHIFT
    BG_MASK = 7 << BG_SHIFT
    
    # In this state we normally start
    DEFAULT_COLOR = COLOR_WHITE
    
    def __init__(self):
        self.ansi_enabled = True
        self.reset_code = '0'
        self.bold_on_code = '1'
        self.bold_off_code = '22'
        self.high_on_code = '4' # It's blink actually, but works as highlight background on many consoles
                                # alternatively use 3 (italic) or 4 (underline)
        self.high_off_code = '24'
        self.inv_on_code = '7'
        self.inv_off_code = '27'
        
        self.fg_start = '3'
        self.bg_start = '4'
        self.sgr_start = "\x1b["
        self.sgr_sep = ';'
        self.sgr_end = 'm'
    
    def wrap_sgr_seq(self, seq):
        if not self.ansi_enabled:
            return ''
        return self.sgr_start + seq + self.sgr_end;

term = Term()

class TermLine(object):
    def __init__(self):
        self.start()
    
    def start(self):
        self.line_as_list = []
        self.line = None
        self.color = term.DEFAULT_COLOR
    
    def get_line(self):
        if self.line != None:
            return self.line
        if self.color != term.DEFAULT_COLOR:
            self.set_color(term.DEFAULT_COLOR)
        self.line = ''.join(self.line_as_list)
        self.line_as_list = [ self.line ]
        return self.line
    
    def append(self, s):
        self.line = None
        self.line_as_list.append(s)
    
    def append_seq(self, seq):
        self.line = None
        self.line_as_list += seq
    
    def set_color(self, color):
        
        # ANSI codes disabled
        if not term.ansi_enabled:
            self.color = color
        
        # No change
        if color == self.color:
            return
        
        # Reset generated line to force re-generation
        self.line = None
        
        # Start SGR (Select Graphic Rendition) sequence
        self.line_as_list.append(term.sgr_start)
        
        # Resetting to default color - just empty sequence to reset
        if color == term.DEFAULT_COLOR:
            self.line_as_list.append(term.sgr_end)
            self.color = term.DEFAULT_COLOR
            return
        
        attr_off = ~color & self.color & term.ATTR_MASK
        # If any attribute is being disabled and color changes, just start from reset
        if (attr_off != 0 and ((color ^ self.color) & ~term.ATTR_MASK)):
            self.line_as_list += ( term.reset_code, term.sgr_sep )
            self.color = term.DEFAULT_COLOR
            attr_off = 0
        attr_on = color & ~self.color & term.ATTR_MASK
        
        # Turn off attributes
        first = True
        if attr_off:
            if attr_off & term.BOLD:
                if not first:
                    self.line_as_list.append(term.sgr_sep)
                self.line_as_list.append(term.bold_off_code)
                first = False
            
            if attr_off & term.HIGHLIGHT:
                if not first:
                    self.line_as_list.append(term.sgr_sep)
                self.line_as_list.append(term.high_off_code)
                first = False
            
            if attr_off & term.INVERSE:
                if not first:
                    self.line_as_list.append(term.sgr_sep)
                self.line_as_list.append(term.inv_off_code)
                first = False
        
        # Turn on attributes
        if attr_on:
            if attr_on & term.BOLD:
                if not first:
                    self.line_as_list.append(term.sgr_sep)
                self.line_as_list.append(term.bold_on_code)
                first = False
            
            if attr_on & term.HIGHLIGHT:
                if not first:
                    self.line_as_list.append(term.sgr_sep)
                self.line_as_list.append(term.high_on_code)
                first = False
            
            if attr_on & term.INVERSE:
                if not first:
                    self.line_as_list.append(term.sgr_sep)
                self.line_as_list.append(term.inv_on_code)
                first = False
        
        # Change foreground
        if (color ^ self.color) & term.FG_MASK:
            if not first:
                self.line_as_list.append(term.sgr_sep)
            self.line_as_list += ( term.fg_start, chr((color & term.FG_MASK) + 0x30) )
            first = False
        
        # Change background
        if (color ^ self.color) & term.BG_MASK:
            if not first:
                self.line_as_list.append(term.sgr_sep)
            self.line_as_list += ( term.bg_start, chr(((color & term.BG_MASK) >> term.BG_SHIFT) + 0x30) )
        
        self.line_as_list.append(term.sgr_end)
        self.color = color
    
    def set_attrib(self, attrib, state):
        attrib &= term.ATTR_MASK
        if state:
            new_color = self.color | attrib
        else:
            new_color = self.color & ~attrib
        self.set_color(new_color)
    
    def set_foreground(self, color):
        new_color = (self.color & ~term.FG_MASK) | (color & term.FG_MASK)
        self.set_color(new_color)
    
    def set_background(self, color):
        new_color = (self.color * ~term.BG_MASK) | (color & term.BG_MASK)
        self.set_color(new_color)
    
    def reset(self):
        self.set_color(term.DEFAULT_COLOR)
    