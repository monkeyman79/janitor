
"""Library functions for 'info janitor registers' and 'info janitor cpu-flags' commands."""

import gdb

import janitor.ansiterm
from janitor.ansiterm import term
import janitor.typecache

FLAGS_BITMASK_COLOR = term.COLOR_WHITE
FLAGS_VALUE_RESET_COLOR = term.COLOR_MAGENTA
FLAGS_VALUE_SET_COLOR = term.COLOR_MAGENTA | term.BOLD
FLAGS_VALUE_NAME_RESET_COLOR = term.COLOR_YELLOW
FLAGS_VALUE_NAME_SET_COLOR = term.COLOR_YELLOW | term.BOLD
FLAGS_NAME_RESET_COLOR = term.COLOR_YELLOW
FLAGS_NAME_SET_COLOR = term.COLOR_YELLOW | term.BOLD
FLAGS_DESCRIPTION_RESET_COLOR = term.COLOR_CYAN
FLAGS_DESCRIPTION_SET_COLOR = term.COLOR_CYAN | term.BOLD

VALUE_CHANGED_ATTR = term.HIGHLIGHT

REG_LABEL_COLOR = term.COLOR_CYAN | term.BOLD
REG_VALUE_COLOR = term.COLOR_MAGENTA | term.BOLD

# flags & eflags:
# ( mask, short_set, short_reset, long_name, group, set, reset )
i386_flags_list = ( ( 0x800, "OV", "NV", "Overflow", "Status" ),
              ( 0x400, "DN", "UP", "Direction", "Control", "Down", "Up" ),
              ( 0x200, "EI", "DI", "Interrupt Enable", "Control", "Enabled", "Disabled" ),
              ( 0x80, "NG", "PL", "Sign", "Status", "Negative", "Positive" ),
              ( 0x40, "ZR", "NZ", "Zero", "Status", "Zero", "Not zero" ),
              ( 0x10, "AC", "NA", "Adjust", "Status" ), # Conflicts with Alignment Check name
              ( 0x4, "PE", "PO", "Parity", "Status", "Parity even", "Parity odd" ),
              ( 0x1, "CY", "NC", "Carry", "Status") )
    
i386_eflags_list = ( ( 0x200000, "ID", "--", "CPUID Available", "System", "Available", "Not available" ),
               ( 0x100000, "VIP", "---", "Virtual Interrupt Pending", "System", "Pending", "Not pending" ),
               ( 0x80000, "VIF", "---", "Virtual Interrupt", "System", "Enabled", "Disabled" ),
               ( 0x40000, "AC", "--", "Alignment Check", "System", "Enabled", "Disabled" ),
               ( 0x20000, "VM", "--", "Virtual 8086 Mode", "System", "Set", "Not set"),
               ( 0x4000, "NT", "--", "Nested Task", "System", "Set", "Not set" ) )
    
# registers:
# ( name, width, label, mask, shift )
# ( name, flags_definition )
# string_literal
i386_first_line = ( ( "eax", 8 ), ( "ebx", 8 ), ( "ecx", 8 ), 
            ( "edx", 8 ), ( "esi", 8 ), ( "edi", 8 ) )
    
i386_second_line = ( ( "eip", 8 ), ( "esp", 8 ), ( "ebp", 8 ), 
            ( "eflags", 8, "FLAGS" ), ( "eflags", i386_flags_list ) )
    
i386_third_line = ( ( "cs", 4 ), ( "ss", 4 ), ( "ds", 4 ), ( "es", 4 ), ( "fs", 4 ), ( "gs", 4 ),
                   ( "eflags", 1, "IOPL", 3, 12 ), "   ", ( "eflags", i386_eflags_list ) )

i386_lines = ( i386_first_line, i386_second_line, i386_third_line )

# list of all registers to save
i386_registers = ( "eax", "ebx", "ecx", "edx", "esi", "edi", "eip", "esp", "ebp", "eflags", "cs", "ss", "ds", "fs", "gs" )

# Just a stub object as there is only one known cpu
class CpuDef(object):
    def __init__(self, regs, flags_reg, lines_list, flags_list, widest_register_type):
        self.regs = regs
        self.flags_reg = flags_reg
        self.lines_list = lines_list
        self.flags_list = flags_list
        self.widest_register_type = widest_register_type

i386_def = CpuDef(i386_registers, "eflags", i386_lines, i386_eflags_list + i386_flags_list, "unsigned long")

cpu_def = i386_def

# previous registers value
prev_registers = {}

# current registers value
curr_registers = {}

def save_registers():
    global prev_registers, curr_registers
    try:
        frame = gdb.newest_frame()
        arch = frame.architecture().name()
    except:
        curr_registers = {}
        prev_registers = {}
    
    if not frame.is_valid():
        return
    
    if not is_supported_arch(arch):
        return
    
    reg_list = cpu_def.regs
    reg_count = len(reg_list)
    reg_num = 0
    prev_registers = curr_registers
    curr_registers = {}
    
    while reg_num < reg_count:
        reg_name = reg_list[reg_num]
        wide_type = janitor.typecache.cache.get_type(cpu_def.widest_register_type)
        if wide_type != None:
            curr_registers[reg_name] = int(frame.read_register(reg_name).cast(wide_type))
        else:
            curr_registers[reg_name] = frame.read_register(reg_name)
        reg_num += 1

def stop_handler(event):
    save_registers()

def exited_handler(event):
    global prev_registers, curr_registers
    curr_registers = {}
    prev_registers = {}

def explain_flags(value, prev_value, flags):
    
    termline =  janitor.ansiterm.TermLine()
    
    flags_count = len(flags)
    flag_num = 0
    while flag_num < flags_count:
        flag = flags[flag_num]
        flag_set = ((value & flag[0]) != 0)
        changed = prev_value != None and ((prev_value ^ value) & flag[0])
        changed_attr = VALUE_CHANGED_ATTR if changed else 0
        
        termline.start()
        
        termline.set_color(FLAGS_BITMASK_COLOR)
        termline.append("%08x" % flag[0])
        termline.reset()
        termline.append(": ")
        
        termline.set_color((FLAGS_VALUE_SET_COLOR if flag_set else FLAGS_VALUE_RESET_COLOR) | changed_attr)
        termline.append("%d" % flag_set)
        termline.reset()
        termline.append(":")
        
        name = "%3s" % flag[2 - flag_set]
        if len(name) < 3:
            termline.append(" ")
        termline.set_color((FLAGS_VALUE_NAME_SET_COLOR if flag_set else FLAGS_VALUE_NAME_RESET_COLOR) | changed_attr)
        termline.append(name)
        termline.reset()
        termline.append(": ")
        
        termline.set_color(FLAGS_NAME_SET_COLOR if flag_set else FLAGS_NAME_RESET_COLOR)
        termline.append("%s Flag" % flag[3])
        termline.reset()
        termline.append(": ")

        termline.set_color(FLAGS_DESCRIPTION_SET_COLOR if flag_set else FLAGS_DESCRIPTION_RESET_COLOR)
        
        if flag_set:
            termline.append(flag[5] if len(flag) >= 6 else flag[3] + " set")
        else:
            termline.append(flag[6] if len(flag) >= 7 else "No " + flag[3].lower())
        
        termline.reset()
        
        print termline.get_line()
        flag_num += 1

def explain_frame_flags(frame):
    eflags = frame.read_register(cpu_def.flags_reg)
    if frame == gdb.newest_frame() and cpu_def.flags_reg in prev_registers:
        prev_eflags = prev_registers[cpu_def.flags_reg]
    else:
        prev_eflags = None
    explain_flags(eflags, prev_eflags, cpu_def.flags_list)


def format_register(termline, label, width, value, prev_value):
    termline.set_color(REG_LABEL_COLOR)
    termline.append(label)
    termline.reset()
    
    termline.append("=")
    
    termline.set_color(REG_VALUE_COLOR)
    termline.set_attrib(VALUE_CHANGED_ATTR, prev_value != None and value != prev_value)
    termline.append("%0*X" % (width, value))
    termline.reset()

def format_register_flags(termline, value, prev_value, flags):
    result = ""
    flags_count = len(flags)
    flag_num = 0
    while flag_num < flags_count:
        flag = flags[flag_num]
        if flag_num > 0:
            termline.append(" ")
        changed = prev_value != None and ((value ^ prev_value) & flag[0])
        changed_attr = VALUE_CHANGED_ATTR if changed else 0
        if value & flag[0]:
            termline.set_color(FLAGS_VALUE_NAME_SET_COLOR | changed_attr)
            termline.append(flag[1])
        else:
            termline.set_color(FLAGS_VALUE_NAME_RESET_COLOR | changed_attr)
            termline.append(flag[2])
        termline.reset()
        flag_num += 1

def print_frame_regs(frame):
    lines = cpu_def.lines_list
    line_count = len(lines)
    line_num = 0
    
    termline = janitor.ansiterm.TermLine()
    
    # Iterate over lines to display
    while line_num < line_count:
        line = lines[line_num]
        
        termline.start()
        elem_count = len(line)
        elem_num = 0
        
        # Iterate over registers in current line
        while elem_num < elem_count:
            elem = line[elem_num]
            if type(elem) is str:
                # Just a string to insert in line
                termline.append(elem)
                elem_num += 1
                continue
            
            if elem_num > 0:
                termline.append(" ")
                
            elem_len = len(elem)
            reg_name = elem[0]
            
            # Read register value
            value = frame.read_register(reg_name)
            
            # Previous register value
            if frame == gdb.newest_frame() and reg_name in prev_registers:
                prev_value = prev_registers[reg_name]
            else:
                prev_value = None
            
            if type(elem[1]) is tuple:
                # It's a flags register
                flags = elem[1]
                format_register_flags(termline, value, prev_value, flags)
                elem_num += 1
                continue
           
            width = elem[1]
            
            # Use register name in uppercase unless label is specified
            if elem_len > 2:
                label = elem[2]
            else:
                label = reg_name.upper()
            
            # Mask
            if elem_len > 3:
                value &= elem[3]
                if prev_value != None:
                    prev_value &= elem[3]
            
            # Shift
            if elem_len > 4:
                value >>= elem[4]
                if prev_value != None:
                    prev_value &= elem[4]
            
            format_register(termline, label, width, value, prev_value)
            
            elem_num += 1
        
        print termline.get_line()
        
        line_num += 1

def is_supported_arch(arch):
    if arch != "i386" and arch != "i8086" and arch != "i386:x86-64":
        return False
    return True