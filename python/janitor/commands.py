
import gdb
import gdb.prompt
import gdb.command.prompt

import janitor.registers
import janitor.disassemble
import janitor.dump
import janitor.prompt
import janitor.typecache
import janitor.ansiterm
from janitor.dump import get_frame_pc
from janitor.dump import get_frame_sp
from janitor.dump import cast_val_to_intptr

def cast_to_intptr(expr):
    return cast_val_to_intptr(gdb.parse_and_eval(expr))

class Hooks(object):
    
    hooks_set = False
    save_enabled = False
    display_enabled = False
    disassemble_next_enabled = False
    
    @staticmethod
    def clear_type_cache():
        janitor.typecache.cache.clear()

    @staticmethod
    def stop_handler(event):
        
        # janitor.disassemble.save_pc()
        
        if Hooks.save_enabled:
            janitor.registers.stop_handler(event)
        
        if Hooks.display_enabled:
            try:
                frame = gdb.newest_frame()
                if not frame.is_valid():
                    return
                arch = frame.architecture().name()
                if janitor.registers.get_cpu_def(arch) is None:
                    return
                janitor.registers.print_frame_regs(frame)
            except:
                pass
        
        if Hooks.disassemble_next_enabled:
            flavor = None
            try:
                flavor = gdb.parameter("disassembly-flavor")
            except:
                pass
            if gdb.newest_frame().is_valid():
                start_address = get_frame_pc(gdb.newest_frame())
                janitor.disassemble.saved_pc = start_address
                janitor.disassemble.start_address = janitor.disassemble.disassemble(gdb.newest_frame().architecture(), start_address, start_address, flavor)

    @staticmethod
    def exited_handler(event):
        if Hooks.save_enabled:
            janitor.registers.exited_handler(event)
    
    @staticmethod
    def clear_objfiles_handler(progspace):
        Hooks.clear_type_cache()

    @staticmethod
    def new_objfile_handler(objfile):
        Hooks.clear_type_cache()

    @staticmethod
    def connect():
        if not Hooks.hooks_set:
            gdb.events.stop.connect(Hooks.stop_handler)
            gdb.events.exited.connect(Hooks.exited_handler)
            gdb.events.new_objfile.connect(Hooks.new_objfile_handler)
        if hasattr(gdb.events, 'clear_objfiles'):
            gdb.events.clear_objfiles.connect(Hooks.clear_objfiles_handler)
        Hooks.hooks_set = True

    @staticmethod
    def disconnect():
        if Hooks.hooks_set:
            gdb.events.stop.disconnect(Hooks.stop_handler)
            gdb.events.exited.disconnect(Hooks.exited_handler)
            gdb.events.new_objfile.disconnect(Hooks.new_objfile_handler)
        if hasattr(gdb.events, 'clear_objfiles'):
            gdb.events.clear_objfiles.disconnect(Hooks.clear_objfiles_handler)
        Hooks.hooks_set = False

class JanitorPrefixCommand(gdb.Command):
    """Janitor is support package for assembly level debugging.
It brings debug.exe look to GDB command line interface.
Additionally it provides advanced prompt substitution."""
    def __init__(self):
        super(JanitorPrefixCommand, self).__init__("janitor",
                                              gdb.COMMAND_DATA,
                                              gdb.COMMAND_NONE,
                                              True)

class JanitorSetPrefixCommand(gdb.Command):
    __doc__ = JanitorPrefixCommand.__doc__
    def __init__(self):
        super(JanitorSetPrefixCommand, self).__init__("set janitor",
                                              gdb.COMMAND_DATA,
                                              gdb.COMMAND_NONE,
                                              True)

class JanitorShowPrefixCommand(gdb.Command):
    __doc__ = JanitorPrefixCommand.__doc__
    def __init__(self):
        super(JanitorShowPrefixCommand, self).__init__("show janitor",
                                              gdb.COMMAND_DATA,
                                              gdb.COMMAND_NONE,
                                              True)

class JanitorInfoPrefixCommand(gdb.Command):
    __doc__ = JanitorPrefixCommand.__doc__
    def __init__(self):
        super(JanitorInfoPrefixCommand, self).__init__("info janitor",
                                              gdb.COMMAND_DATA,
                                              gdb.COMMAND_NONE,
                                              True)

class PromptParameter(gdb.Parameter):
    """Usage: set janitor prompt VALUE
       show jantor prompt
       janitor eval prompt VALUE

All substitutions are enclosed between '${' and '}'. Defined substitutions are:

${r:reg}               Value of register in selected frame.
${v:var}               Value of variable in selected frame.
${fn}                  Selected frame number
${f[:attr]}            Selected frame attribute.
                       Frame attribute can be one of: `is_valid`, `num`, `name`, `architecture`, `pc`, `type`, `unwind_stop_reason`.
                       Default is `is_valid`

${nr:reg}              Value of register in newest frame.
${nv:var}              Value of variable in newest frame.
${n[:attr]}            Newest frame attribute.

${tn}                  Selected thread number
${t:[attr]}            Selected thread attribute.
                       Thread attribuet can be one of: `is_valid`, `num`, `name`, `global_num`, `pid`, `lwpid`, `tid`, `is_stopped`, `is_running`, `is_exited`.
                       Default is `is_valid`

${p:param}             Value of GDB parameter

${g:exp}               Expression value evaluated by GDB. Substitutions are converted to strings before evaluation.
${e:exp}               Expression value evaluated in Python. Substitutions are passed as variable to evaluation.
${?subst:if_true[:if_false]} Substitute `if_true` if `subst` evaluates to true, otherwise substitute `if_false`.
                       The `subst` expression undergoes substitution and then is evaluated in Python.
${?:subst[:if_false]}  Substitute `subst` if it is anything different than None and empty string, otherwise substitute `if_false`.
${:exps}               Concatenation, evaluates and concatenates expressions. Can be also used to apply formatting.
${[SEQ}                If ANSI sequences are enabled, evaluates to ANSI escape sequence \e[SEQm, otherwise - empty string

Formatting:

    Append `|format` inside substitution brackets to format resulting value.


Type casting:

    Append `#type[%string_conversion]` inside substitution brackets to cast resulting value. Cast operation works differently for
    values of type gdb.Value and for all other types.
    
    For gdb values it is possible to cast to any known type, using `#(full type name)` or use
    abbreviations for some well known types:
        [s|u]c   - [signed|unsigned] char
        [u]s     - [unsigned] short
        [u]i     - [unsigned] int
        [u]l     - [unsigned] long
        [u]ll    - [unsigned] long long
        f        - float
        d        - double
        ld       - long double
        func     - void ()
    Prepend 'p' to abbreviation to turn it into pointer to given type.

    For non-gdb values reasonable casts are:
        pc -    Convert to string
        i -     Convert to integer value
        f -     Convert to floating point value

    Optional `string_conversion` specifier applies only to values of type gdb.Value. Allowed values are:
        s  -    Call gdb.Value.string() method on the value to convert it to Python string
        e  -    Convert to Python string and escape non-printable characters as in C
        r  -    Convert to Python string and remove non-printable characters
        t  -    Insert ANSI term sequences to produce result as characters displayed by `janitor dump` command
        
Inside `{?subst:true:false}`, each of `true` and `false` can be followed by a format or cast specifier
(ie. terminating `|format` applies to `false` part only).
To apply format to both parts, use `{:{?subst:true:false}|format}`.

Use backslash to escape characters from special interpretation: '\$', '\{', '\}', '\:', `\|`, `\#`.

Examples:

    ${?${f:num}!=0:[${f:num}]}              - expands to frame number enclosed in square brackets
                                              if selected frame is not top frame.
    ${?${r:cs}==${nr:cs}:cs:${r:cs|%08X}}  - expands to 'cs' if value of cs register in selected frame
                                              is the same as the register's value in top frame,
                                              otherwise it expands to value of cs formated as hexadecimal
                                              number.

Apart from '${}' substitutions, backslash substitutions from extended-prompt apply:

"""
    __doc__ = __doc__ + gdb.prompt.prompt_help()

    set_doc = "Set the advanced prompt."
    show_doc = "Show the advanced prompt."

    def __init__(self):
        super(PromptParameter, self).__init__("janitor prompt",
                                              gdb.COMMAND_SUPPORT,
                                              gdb.PARAM_STRING_NOESCAPE)
        self.value = ''

    def get_show_string(self, pvalue):
        if self.value is not '':
            return "The advanced prompt is: " + self.value
        else:
            return "The advanced prompt is not set."

    def get_set_string(self):
        if self.value == '':
            if gdb.prompt_hook == self.before_prompt_hook:
                gdb.prompt_hook = None;
                return "Advanced prompt disabled."
            return "";
        
        if gdb.prompt_hook != self.before_prompt_hook:
            # Take prompt substitution from _ExtendedPrompt
            gdb.command.prompt._ExtendedPrompt.hook_set = False
            gdb.prompt_hook = self.before_prompt_hook
            # Reset type cache on new objects
            Hooks.connect()
            return "Advanced prompt enabled."
        
        return "Advanced prompt set"

    def before_prompt_hook(self, current):
        if self.value is not '':
            return janitor.prompt.substitute_value_prompt_str(self.value)
        else:
            return None

class EvaluatePromptCommand(gdb.Command):
    """Evaluate advanced prompt without actually changing the prompt.
"""

    __doc__ += PromptParameter.__doc__
    
    def __init__(self):
        super(EvaluatePromptCommand, self).__init__("janitor eval",
                                                        gdb.COMMAND_SUPPORT)
    def invoke(self, arg_str, from_tty):
        print(janitor.prompt.substitute_value_prompt_str(arg_str))
        return



class InfoRegistersCommand(gdb.Command):
    """Print registers in low-level debugger style."""
    
    def __init__(self):
        super(InfoRegistersCommand, self).__init__(name="info janitor registers",
                                    command_class = gdb.COMMAND_STATUS)
    
    def invoke(self, arg_str, from_tty):
        try:
            frame = gdb.selected_frame()
        except gdb.error as e:
            print("Cannot access selected frame: " + str(e))
            return

        if not frame.is_valid():
            print("Selected frame is not valid.")
            return

        arch = frame.architecture().name()
        if janitor.registers.get_cpu_def(arch) is None:
            print("This command is supported only for i386 or arm architectures.")
            return

        janitor.registers.print_frame_regs(frame)

class InfoFlagsCommand(gdb.Command):
    """Print detailed info on flags register."""
    
    def __init__(self):
        super(InfoFlagsCommand, self).__init__(name="info janitor cpu-flags",
                                    command_class = gdb.COMMAND_STATUS)
    
    def invoke(self, arg_str, from_tty):
        try:
            frame = gdb.selected_frame()
        except gdb.error as e:
            print("Cannot access selected frame: " + str(e))
            return
        
        if not frame.is_valid():
            gdb.GdbError("Selected frame is not valid.");

        arch = frame.architecture().name()
        if janitor.registers.get_cpu_def(arch) is None:
            print("This command is supported only for i386 or arm architecture.")
            return
        
        janitor.registers.explain_frame_flags(frame)

    
class RegistersSaveParameter(gdb.Parameter):
    """Usage: set janitor registers-save [on|off]
       show janitor registers-save"""
    
    set_doc = "Enable or disable saving and highlighting changed registers."
    
    show_doc = "Show whether saving and highlighting changed registers is activated."
    
    def __init__ (self):
        super(RegistersSaveParameter, self).__init__("janitor registers-save",
                                                                gdb.COMMAND_STATUS,
                                                                gdb.PARAM_BOOLEAN)
        self.value = False
    
    def get_show_string (self, pvalue):
        return "Saving cpu registers is " + ("enabled." if self.value else "disabled.")

    def get_set_string (self):
        if self.value == Hooks.save_enabled:
            return "Saving cpu registers is " + ("enabled." if self.value else "disabled.")
        if self.value:
            Hooks.connect()
        else:
            janitor.registers.prev_registers = {}
            janitor.registers.curr_registers = {}
        Hooks.save_enabled = self.value
        return "Saving cpu registers " + ("enabled." if self.value else "disabled.")

class RegistersOnStopParameter(gdb.Parameter):
    """Usage: set janitor registers-on-stop [on|off]
       show janitor registers-on-stop"""
    
    set_doc = "Enable or disable showing cpu registers on stop."
    
    show_doc = "Display whether showing cpu registers on stop is activated."
    
    def __init__ (self):
        super(RegistersOnStopParameter, self).__init__("janitor registers-on-stop",
                                                                gdb.COMMAND_STATUS,
                                                                gdb.PARAM_BOOLEAN)
        self.value = False
    
    def get_show_string (self, pvalue):
        return "Display cpu registers on stop is " + ("enabled." if self.value else "disabled.")

    def get_set_string (self):
        if self.value == Hooks.display_enabled:
            return "Display cpu registers on stop is " + ("enabled." if self.value else "disabled.")
        if self.value:
            Hooks.connect()
        Hooks.display_enabled = self.value
        return "Display cpu registers on stop " + ("enabled." if self.value else "disabled.")

class AnsiParameter(gdb.Parameter):
    """Usage: set janitor ansi [on|off]
       show janitor ansi"""
    
    set_doc = "Enable or disable using ANSI terminal sequences."
    
    show_doc = "Display whether ANSI terminal sequences are being used."
    
    def __init__ (self):
        super(AnsiParameter, self).__init__("janitor ansi",
                                            gdb.COMMAND_SUPPORT,
                                            gdb.PARAM_BOOLEAN)
        self.value = True
    
    def get_show_string (self, pvalue):
        return "Use of ANSI terminal sequences is " + ("enabled." if self.value else "disabled.")

    def get_set_string (self):
        janitor.ansiterm.term.ansi_enabled = self.value
        return "ANSI terminal sequences " + ("enabled." if self.value else "disabled.")

def split_on_commas(expr):
    result = []
    if expr == None or expr == "":
        return result
    level = 0
    index = 0
    start = 0
    length = len(expr)
    while index < length:
        if level == 0 and expr[index] == ',':
            result.append(expr[start:index].strip())
            start = index + 1
        elif expr[index] == '(':
            level += 1
        elif expr[index] == ')':
            if level <= 1:
                gdb.GdbError("invalid arguments")
            level -= 1
        index += 1
    result.append(expr[start:].strip())
    return result

    

class DisassembleCommand(gdb.Command):
    """Disassemble in low-level debugger style with colors

Usage: janitor disassemble [start] [,end|,+length]"""

    def __init__(self):
        super(DisassembleCommand, self).__init__("janitor disassemble",
                                                        gdb.COMMAND_DATA,
                                                        gdb.COMPLETE_EXPRESSION)
        ## For reset address on stop
        #Hooks.connect()
    
    def invoke(self, arg_str, from_tty):
        intptr_type = None
        argv = split_on_commas(arg_str)
        
        if len(argv) > 2:
            raise gdb.GdbError ("too many arguments")
        
        # disassemble +1 -> disassemble ,+1
        if len(argv) == 1 and len(argv[0]) > 0 and argv[0][0] == '+':
            argv = ( "", argv[0] )
        
        # Reset start_address to current PC is selected frame has changed
        if (janitor.disassemble.saved_pc != None and
                gdb.selected_frame().is_valid() and 
                (janitor.disassemble.saved_pc == False or
                get_frame_pc(gdb.selected_frame()) != janitor.disassemble.saved_pc)):
            janitor.disassemble.saved_pc = None
            janitor.disassemble.start_address = None
        
        start_address = janitor.disassemble.start_address
        if len(argv) > 0 and argv[0] != "":
            start_address = cast_to_intptr(argv[0])
            # Hmm.. if user disassembles from pc and switches frames
            # it will restart from new frame's pc.
            # I'm not sure if that's good feature.
            if start_address == get_frame_pc(gdb.selected_frame()):
                janitor.disassemble.saved_pc = start_address
        elif start_address == None:
            if gdb.selected_frame().is_valid():
                start_address = get_frame_pc(gdb.selected_frame())
                janitor.disassemble.saved_pc = start_address
            else:
                raise gdb.GdbError ("no start address")
        
        if len(argv) > 1 and argv[1] != "":
            if argv[1][0] == '+':
                length = cast_to_intptr(argv[1][1:])
                janitor.disassemble.length = length
                end_address = start_address + length
            else:
                end_address = cast_to_intptr(argv[1])
                janitor.disassemble.length = None
        elif janitor.disassemble.length != None:
            end_address = start_address + janitor.disassemble.length
        else:
            end_address = None
        
        flavor = None
        try:
            flavor = gdb.parameter("disassembly-flavor")
        except:
            pass
        
        if end_address == None or end_address >= start_address:
            janitor.disassemble.start_address = janitor.disassemble.disassemble(gdb.selected_frame().architecture(), start_address, end_address, flavor)

class DisassembleNextInstrParameter(gdb.Parameter):
    """Usage: set janitor disassemble-next-instr [on|off]
       show janitor disassemble-next-instr"""
    
    set_doc = "Enable or disable disassembling next instruction on stop."
    
    show_doc = "Display whether disassembling next instruction on stop is activated."
    
    def __init__ (self):
        super(DisassembleNextInstrParameter, self).__init__("janitor disassemble-next-instr",
                                                                gdb.COMMAND_STATUS,
                                                                gdb.PARAM_BOOLEAN)
        self.value = False
    
    def get_show_string (self, pvalue):
        return "Disassemble on stop is " + ("enabled." if self.value else "disabled.")

    def get_set_string (self):
        if self.value == Hooks.disassemble_next_enabled:
            return "Disassemble on stop is " + ("enabled." if self.value else "disabled.")
        if self.value:
            Hooks.connect()
        Hooks.disassemble_next_enabled = self.value
        return "Disassemble on stop " + ("enabled." if self.value else "disabled.")


class DumpCommand(gdb.Command):
    """Dump memory in low-level debugger style with colors
Usage: janitor dump [/fmt] [start] [,end|,+length]

The /fmt parameter is different from the one used in x or print command.
There is no repeat count or format letter, instead it consists of size and endianness.
Size letters are 1/b - byte, 2/h/s - 2 bytes, 4/d/l - 4 bytes, 8/g/q - 8 bytes, w - configured word size.
Endianness letters are l - little endian, b - big endian.

Order of size and endianness letter is not significant, `b` and `l` are interpreted as endianness letter only
if accompanied with size letter.

Size of word can be configured with set `janitor word-size`."""

    def __init__(self):
        super(DumpCommand, self).__init__("janitor dump",
                                                        gdb.COMMAND_DATA,
                                                        gdb.COMPLETE_EXPRESSION)
    
    def invoke(self, arg_str, from_tty):
        
        fmt = None
        
        if len(arg_str)>0 and arg_str[0] == '/':
            fmt, sep, arg_str = arg_str[1:].partition(' ')
        
        argv = split_on_commas(arg_str)
        
        if len(argv) > 2:
            raise gdb.GdbError ("too many arguments")
        
        if len(argv) == 1 and len(argv[0]) > 0 and argv[0][0] == '+':
                argv = ( "", argv[0] )
            
        start_address = janitor.dump.start_address
        if len(argv) > 0 and argv[0] != "":
            start_address = cast_to_intptr(argv[0])
            janitor.dump.highlight_start = None
            janitor.dump.highlight_end = None
            # If address is specified and previously was dumping stack
            # restore pre-stack format
            if janitor.dump.saved:
                janitor.dump.saved = False
                janitor.dump.width = janitor.dump.saved_width
                janitor.dump.endian = janitor.dump.saved_endian
        
        elif start_address == None:
            raise gdb.GdbError ("no start address")
        
        if fmt != None:
            janitor.dump.parse_format(fmt)
        
        if janitor.dump.width == None:
            janitor.dump.width = 1
        
        if janitor.dump.endian == None:
            # This will work only if user explicitly sets endianness with 'set endian'
            # I don't know any way to ask gdb about default architecture endianness
            user_endian = gdb.parameter("endian")
            if user_endian == "big":
                janitor.dump.endian = janitor.dump.BIG_ENDIAN
        

        if len(argv) > 1 and argv[1] != "":
            if argv[1][0] == '+':
                length = cast_to_intptr(argv[1][1:])
                janitor.dump.length = length
                end_address = start_address + length
            else:
                end_address = cast_to_intptr(argv[1])
                janitor.dump.length = None
        elif janitor.dump.length != None:
            end_address = start_address + janitor.dump.length
        else:
            end_address = None
        
        if end_address == None or end_address >= start_address:
            janitor.dump.start_address = janitor.dump.dump(start_address, end_address)

class DumpStackCommand(gdb.Command):
    """Dump raw stack in low-level debugger style with colors.
Usage: janitor raw-stack [/fmt] [+length]

Displays stack correctly only on architectures where stack grows downward.
See `janitor dump` command for description of /fmt.
"""

    def __init__(self):
        super(DumpStackCommand, self).__init__("janitor raw-stack",
                                                        gdb.COMMAND_DATA,
                                                        gdb.COMPLETE_EXPRESSION)
    
    def invoke(self, arg_str, from_tty):
        
        if not janitor.dump.saved:
            janitor.dump.saved = True
            janitor.dump.saved_width = janitor.dump.width
            janitor.dump.saved_endian = janitor.dump.endian
        
        janitor.dump.width = janitor.dump.format_width['w']
        
        if len(arg_str)>0 and arg_str[0] == '/':
            fmt, sep, arg_str = arg_str[1:].partition(' ')
            janitor.dump.parse_format(fmt)
        
        if janitor.dump.endian == None:
            # This will work only if user explicitly sets endianness with 'set endian'
            # I don't know any way to ask gdb about default architecture endianness
            user_endian = gdb.parameter("endian")
            if user_endian == "big":
                janitor.dump.endian = janitor.dump.BIG_ENDIAN
        
        if janitor.dump.width == None:
            janitor.dump.width = 1
        
        argv = split_on_commas(arg_str)
        
        if len(argv) > 1:
            raise gdb.GdbError ("too many arguments")
        
        if len(argv) == 1 and len(argv[0]) > 0 and argv[0][0] == '+':
                argv = ( "", argv[0] )
        
        start_address = get_frame_sp(gdb.newest_frame())
        janitor.dump.start_address = start_address

        janitor.dump.highlight_start = None
        janitor.dump.highlight_end = None
        
        selected_frame = gdb.selected_frame()
        if selected_frame != None and selected_frame.is_valid():
            janitor.dump.highlight_start = get_frame_sp(selected_frame)
            prev_frame = selected_frame.older()
            if prev_frame != None and prev_frame.is_valid():
                janitor.dump.highlight_end = get_frame_sp(prev_frame)
                if janitor.dump.highlight_start > janitor.dump.highlight_end:
                    tmp = janitor.dump.highlight_end
                    janitor.dump.highlight_end = janitor.dump.highlight_start
                    janitor.dump.highlight_start = tmp
        
        if janitor.dump.highlight_start != None and janitor.dump.highlight_start < janitor.dump.start_address:
            janitor.dump.start_address = janitor.dump.highlight_start
        
        if len(argv) > 0 and argv[0] != "":
            if argv[0][0] == '+':
                length = cast_to_intptr(argv[0][1:])
                janitor.dump.length = length
                end_address = start_address + length
            else:
                end_address = cast_to_intptr(argv[0])
                janitor.dump.length = None
        elif janitor.dump.length != None:
            end_address = start_address + janitor.dump.length
        else:
            end_address = None
        
        if end_address == None or end_address >= start_address:
            janitor.dump.start_address = janitor.dump.dump(start_address, end_address)

    
class DumpWordWidthParameter(gdb.Parameter):
    """Usage: set janitor word-width [2|4]
       show janitor word-width"""
    
    set_doc = "Set default word width for janitor dump command."
    
    show_doc = "Display default word width for janitor dump command."
    
    def __init__ (self):
        super(DumpWordWidthParameter, self).__init__("janitor word-width",
                                                                gdb.COMMAND_STATUS,
                                                                gdb.PARAM_ENUM,
                                                                ("2", "4"))
        self.value = "4"
        janitor.dump.format_width['w'] = 4
    
    def get_show_string (self, pvalue):
        return "Word width is " + str(pvalue) + "."

    def get_set_string (self):
        if self.value != "2" and self.value != "4":
            gdb.GdbError ("invalid word width.")
        janitor.dump.format_width['w'] = 4 if self.value == "4" else 2
        return "Word width set to " + self.value + "."

class DumpLineAlignParameter(gdb.Parameter):
    """Usage: set janitor dump-line-align [on|off]
       show janitor dump-line-align"""
    
    set_doc = "Set dump command line start alignment."
    
    show_doc = "Display dump command line start alignment."
    
    def __init__ (self):
        super(DumpLineAlignParameter, self).__init__("janitor dump-line-align",
                                                                gdb.COMMAND_STATUS,
                                                                gdb.PARAM_BOOLEAN)
        self.value = False
        janitor.dump.dump_obj.ALIGNED = 1
    
    def get_show_string (self, pvalue):
        return "Dump line alignment is " + ("on." if self.value else "off.")

    def get_set_string (self):
        janitor.dump.dump_obj.ALIGNED = 16 if self.value else 1
        return "Dump line alignment " + ("on." if self.value else "off.")

class I8086HackParameter(gdb.Parameter):
    """Usage: set janitor i8086 [on|off]
       show janitor i8086"""
    
    set_doc = "Set i386 real mode hack parameter."
    
    show_doc = "Show i386 real mode hack parameters."
    
    def __init__ (self):
        super(I8086HackParameter, self).__init__("janitor i8086",
                                                                gdb.COMMAND_STATUS,
                                                                gdb.PARAM_BOOLEAN)
        self.value = False
    
    def get_show_string (self, pvalue):
        return "Real mode i386 hack is " + ("on." if self.value else "off.")

    def get_set_string (self):
        janitor.dump.i8086_hack = self.value
        return "Real mode i386 hack " + ("on." if self.value else "off.")
        
JanitorPrefixCommand()
JanitorSetPrefixCommand()
JanitorShowPrefixCommand()
JanitorInfoPrefixCommand()

# set janitor prompt
PromptParameter()
# janitor eval-prompt
EvaluatePromptCommand()

# info janitor registers
InfoRegistersCommand()
# info janitor cpu-flags
InfoFlagsCommand()
# set janitor registers-save
RegistersSaveParameter()
# set janitor registers-on-stop
RegistersOnStopParameter()

# janitor disassemble
DisassembleCommand()
# set janitor disassemble-next-instr
DisassembleNextInstrParameter()

# janitor dump
DumpCommand()
# set janitor word-width
DumpWordWidthParameter()
# set janitor dump-line-align
DumpLineAlignParameter()
# janitor stack
DumpStackCommand()

# set janitor ansi
AnsiParameter()

# set janitor i8086
I8086HackParameter()
