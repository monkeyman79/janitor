
"""Implementation of 'janitor disassemble' command for GDB."""

import gdb

import janitor.ansiterm
from janitor.ansiterm import term
import janitor.dump
from janitor.dump import get_frame_pc

start_address = None
saved_pc = None
length = None

class DecorateArgs(object):
    STATE_NONE = 0
    STATE_REG = 1
    STATE_CONST = 2
    STATE_KEYWORD = 3
    STATE_INDIRECT = 4
    STATE_INDIRECT_REG = 5
    STATE_OFFSET = 6
    STATE_ANNO = 7
    STATE_ANNO_IDEN = 8
    STATE_ANNO_NUMBER = 9
    STATE_INSTR = 10

    # Must be all uppercase
    I386_KEYWORDS = { "BYTE", "SBYTE", "WORD", "SWORD", "DWORD", "SDWORD", "QWORD", "SQWORD", 
            "REAL4", "REAL8", "FLOAT", "DOUBLE", "PTR", "OFFSET" }
    keywords = None

    ARM_REGISTERS = { "R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", 
            "R8", "R9", "R10", "R11", "R12", "SP", "LR", "PC", "CPSR" }
    registers = None

    state_colors = {
        STATE_NONE: term.COLOR_WHITE,
        STATE_REG: term.COLOR_CYAN | term.BOLD,
        STATE_CONST: term.COLOR_MAGENTA | term.BOLD,
        STATE_KEYWORD: term.COLOR_YELLOW,
        STATE_INSTR: term.COLOR_YELLOW | term.BOLD,
        STATE_INDIRECT: term.COLOR_RED | term.BOLD,
        STATE_INDIRECT_REG: term.COLOR_RED,
        STATE_OFFSET: term.COLOR_GREEN,
        STATE_ANNO: term.COLOR_YELLOW,
        STATE_ANNO_IDEN: term.COLOR_GREEN | term.BOLD,
        STATE_ANNO_NUMBER: term.COLOR_GREEN
    }
        

    def __init__(self, arch_name, flavor):
        self.flavor = flavor
        if arch_name == "i386" or arch_name == "i8086" or arch_name == "i386:x86-64":
            self.keywords = self.I386_KEYWORDS
        if arch_name == "arm":
            self.registers = self.ARM_REGISTERS
    
    def new_state(self, state):
        if self.state == state:
            return
        color = self.state_colors[state]
        if color == self.termline.color:
            self.state = state
            return
        if self.index != self.state_start:
            self.termline.append(self.args[self.state_start : self.index])
        self.termline.set_color(color)
        self.state_start = self.index
        self.state = state

    def finish(self):
        if self.args_len != self.state_start:
            self.termline.append(self.args[self.state_start : self.args_len])
        self.state_start = self.args_len
        self.termline.reset()
    
    def peek_identifier(self):
        ptr = self.index + 1
        # To re or not to re?
        while ptr < self.args_len:
            c = self.args[ptr]
            if not c.isalnum() and c != '_':
                break
            ptr += 1
        return self.args[self.index : ptr]

    def invoke(self, args, termline):
        
        self.state = None
        self.termline = termline
        self.index = 0
        self.args = args
        self.state_start = 0
        self.args_len = len(args)
        self.num_paren = 0

        self.new_state(self.STATE_NONE)
        
        self.identifier = False
        self.number = False
        self.ptr = False
        self.first = True
        self.annotation = False
        self.offset = False

        while self.index < self.args_len:
            c = self.args[self.index]
            
            # In annotation
            if self.annotation:
                if c.isalpha() or (c in "_%$#@:"):
                    if not self.identifier and (not self.number or not (c.upper() in "ABCDEFX")):
                        self.identifier = True
                        self.new_state(self.STATE_ANNO_IDEN)
                elif c.isdigit():
                    if not self.identifier and not self.number:
                        self.number = True
                        self.new_state(self.STATE_ANNO_NUMBER)
                elif self.identifier or self.number:
                    self.identifier = False
                    self.number = False
                    self.new_state(self.STATE_ANNO)
            
            # % - Register name
            elif c == '%':
                if not self.identifier:
                    if self.state == self.STATE_INDIRECT:
                        self.new_state(self.STATE_INDIRECT_REG)
                    else:
                        self.new_state(self.STATE_REG)
            
            # $ or # - Assume constant value
            elif c == '$' or c == '#':
                if not self.identifier:
                    self.new_state(self.STATE_CONST)
            
            # * on beginning of number or register - Indirect call
            elif c == '*' and self.first:
                self.new_state(self.STATE_INDIRECT)
                self.identifier = False
                self.number = False
            
            # Count parentheses to determine value type
            elif c == '[' or c == '(':
                self.num_paren += 1;
                self.new_state(self.STATE_NONE)
                self.identifier = False
                self.number = False
            elif c == ']' or c == ')':
                self.num_paren -= 1;
                self.new_state(self.STATE_NONE)
                self.identifier = False
                self.number = False
            
            # Digit starts number, unless part of identifier
            elif c.isdigit():
                if not self.number and not self.identifier:
                    self.number = True
                    # Try to determine value type
                    if self.state == self.STATE_NONE:
                        # after DWORD PTR
                        if self.ptr:
                            if self.num_paren == 0:
                                ## Indirect jump - maybe
                                #self.new_state(self.STATE_INDIRECT)
                                # Offset
                                self.new_state(self.STATE_OFFSET)
                            else:
                                # Offset
                                self.new_state(self.STATE_OFFSET)
                        else:
                            # Bare number - either const or offset. Take a guess.
                            if self.flavor == "intel" and self.num_paren == 0 and not self.offset:
                                self.new_state(self.STATE_CONST)
                            else:
                                self.new_state(self.STATE_OFFSET)
                
                # Skip the number or whatever it is
                self.index += len(self.peek_identifier())
                continue
            
            # Identifier - most likely a register
            elif c.isalpha() or c == '_':
                ident = self.peek_identifier()
                if not self.number and not self.identifier:
                    self.identifier = True
                    if self.keywords is not None and ident.upper() in self.keywords:
                        # Keyword
                        self.new_state(self.STATE_KEYWORD)
                        if ident.upper() == "PTR":
                            self.ptr = True
                    elif self.state == self.STATE_INDIRECT or self.state == self.STATE_INDIRECT_REG:
                        self.new_state(self.STATE_INDIRECT_REG)
                    elif self.registers is not None:
                        if ident.upper() in self.registers:
                            self.new_state(self.STATE_REG)
                        else:
                            # Assume keyword
                            self.new_state(self.STATE_INSTR)
                    else:
                        # Assume register?
                        self.new_state(self.STATE_REG)
                # Skip the identifier
                self.index += len(ident)
                continue
            
            # comma outside parentheses cancels ptr and offset
            elif c == ',':
                self.new_state(self.STATE_NONE)
                self.identifier = False
                self.number = False
                if self.num_paren == 0:
                    self.ptr = False
                    self.offset = False
            
            # : - assume offset following
            #elif c == ':':
            #    self.offset = True
            #    self.new_state(self.STATE_NONE)
            #    self.identifier = False
            #    self.number = False
            
            # < - begins annotation
            elif c == '<':
                self.new_state(self.STATE_ANNO)
                self.annotation = True
            
            # end of number or identifier
            else:
                self.new_state(self.STATE_NONE)
                self.identifier = False
                self.number = False
            
            # for special treatment of *
            if c == ',':
                self.first = True
            else:
                self.first = False
        
            self.index += 1
        
        self.finish()

class Disassemble(janitor.dump.DumpBase):
    CURRENT_PC_COLOR = term.COLOR_GREEN | term.BOLD
    SELECTED_PC_COLOR = term.COLOR_GREEN
    BROKEN_PC_COLOR = term.COLOR_RED | term.BOLD
    ADDRESS_COLOR = term.COLOR_WHITE | term.BOLD
    BYTES_COLOR = term.COLOR_WHITE
    INSTR_COLOR = term.COLOR_YELLOW | term.BOLD
    
    BYTES_PER_LINE = 8
    ARM_BYTES_PER_LINE = 4
    INSTR_WIDTH = 10
    ADDR_WIDTH = 8
    
    def __init__(self):
        super(Disassemble, self).__init__()
    
    def append_pc_indicator(self, length):
        # Indicate current or selected frame pc position
        if self.address == self.current_pc:
            self.termline.set_color(self.CURRENT_PC_COLOR)
            self.termline.append("=>")
        elif self.address == self.selected_pc:
            self.termline.set_color(self.SELECTED_PC_COLOR)
            self.termline.append("->")
        elif (self.current_pc != None and self.address < self.current_pc and self.address + length > self.current_pc or
            self.selected_pc != None and self.address < self.selected_pc and self.address + length > self.selected_pc):
            
            self.termline.set_color(self.BROKEN_PC_COLOR)
            self.termline.append("/>")
        else:
            self.termline.append("  ")
        self.termline.reset()
        self.termline.append(" ")
    
    def append_bytes(self, bytes, padding):
        length = len(bytes)
        
        self.termline.set_color(self.BYTES_COLOR)
        if length > 0: # Unlikely false
            self.termline.append("%02X" % ord(bytes[0]))
        for byte in bytes[1 : self.bytes_per_line]:
            self.termline.append(" %02X" % ord(byte))
        self.termline.reset()
        # padding
        if padding:
            if length < self.bytes_per_line:
                self.termline.append((self.bytes_per_line - length) * "   ")
            self.termline.append(" ")
    
    def invoke(self, arch, start_addr, end_addr, flavor):
        self.termline = janitor.ansiterm.TermLine()
        self.decorate_args = DecorateArgs(arch.name(), flavor)
        self.address = start_addr
        self.current_pc = None
        self.selected_pc = None
        self.bytes_per_line = self.BYTES_PER_LINE
        if (arch.name() == "arm"):
            self.bytes_per_line = self.ARM_BYTES_PER_LINE
        
        count = None
        if gdb.newest_frame().is_valid():
            self.current_pc = get_frame_pc(gdb.newest_frame())
        if gdb.selected_frame().is_valid():
            self.selected_pc = get_frame_pc(gdb.selected_frame())
        
        if end_addr == None:
            height = gdb.parameter("height")
            if height != None:
                count = gdb.parameter("height") / 2 - 2
            else:
                count = 12
            disass = arch.disassemble(start_pc = start_addr, count = count)
        else:
            disass = arch.disassemble(start_pc = start_addr, end_pc = end_addr)
    
        for instr in disass:
            
            self.termline.start()
            
            instr_addr = instr["addr"]
            instr_len = instr["length"]
            instr_asm = instr["asm"]
            
            # PC indicator
            self.append_pc_indicator(instr_len)
            
            # Address
            self.append_address(instr_addr)
            
            # Read instruction bytes
            instr_bytes = gdb.selected_inferior().read_memory(self.address, instr_len)
            
            # First group of bytes
            self.append_bytes(instr_bytes[0 : self.bytes_per_line], True)
            
            # Separate instruction from arguments
            #instr_end = instr_asm.find(' ')
            instr_tmp = instr_asm.split(None, 1)
            instr_asm = instr_tmp[0].strip()
            instr_args = (None if len(instr_tmp) < 2 else instr_tmp[1].strip())
            
            instr_asm_len = len(instr_asm)
            
            # Insert instruction
            self.termline.set_color(self.INSTR_COLOR)
            self.termline.append("%-*s" % (self.INSTR_WIDTH, instr_asm))
            self.termline.reset()
            
            wrap_args = (instr_args != None and instr_asm_len > self.INSTR_WIDTH)
            # Insert decorated instruction arguments in current line, but only if instruction is not too long
            if instr_args != None and not wrap_args:
                self.termline.append(" ")
                self.decorate_args.invoke(instr_args, self.termline)

            # Display line
            print(self.termline.get_line())

            # More lines if something didn't fit
            byte_ptr = self.bytes_per_line
            while instr_len > byte_ptr or wrap_args:
                
                self.termline.start()
                
                # Margin + address space + ' '
                self.termline.append((4 + self.ADDR_WIDTH) * " ")
                
                # Instruction bytes
                if instr_len > byte_ptr:
                    self.append_bytes(instr_bytes[byte_ptr : byte_ptr + self.bytes_per_line], wrap_args)
                    byte_ptr += self.bytes_per_line
                else:
                    # no instruction bytes, just padding for arguments
                    self.termline.append(self.bytes_per_line * "   ")
                
                # Put arguments in second line
                if wrap_args:
                    self.termline.append((self.INSTR_WIDTH + 1) * " ")
                    self.decorate_args.invoke(instr_args, self.termline)
                    wrap_args = False
                
                # Display line
                print(self.termline.get_line())
            
            # Adjust address
            self.address += instr["length"]
        
        return self.address

disassemble_obj = Disassemble()

def disassemble(arch, start_addr, end_addr, flavor):
    return disassemble_obj.invoke(arch, start_addr, end_addr, flavor)

def save_pc():
    global saved_pc
    saved_pc = False

#    global start_address
#    start_address = None
#    length = None
#    
#    try:
#        frame = gdb.newest_frame()
#        
#        if not frame.is_valid():
#            return
#        
#        start_address = frame.pc()
#    
#    except:
#        pass
