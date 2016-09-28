
"""Library functions for set janitor prompt and janitor eval-prompt commands."""

import gdb
import gdb.prompt

import janitor.typecache
import janitor.dump
import janitor.ansiterm

class PrettyPromptException(Exception):
    pass

known_types = {
    "v": "void",
    "c": "char",
    "sc": "signed char",
    "uc": "unsigned char",
    "s": "short",
    "us": "unsigned short",
    "i": "int",
    "ui": "unsigned int",
    "l": "long",
    "ul": "unsigned long",
    "ll": "long long",
    "ull": "unsigned long long",
    "f": "float",
    "d": "double",
    "ld": "long double",
    "func": "void()" }
    
py_string_types = { "c", "sc", "uc", "pc", "psc", "puc" }
py_int_types = { "s", "us", "i", "ui", "l", "ul", "ll", "ull" }
py_float_types = { "f", "d", "ld" }
    
def try_cast(value, expr):
    if len(expr) == 0:
        raise PrettyPromptException()

    string_str = None
    if '%' in expr:
        typestr, _, string_str = expr.partition('%')
    else:
        typestr = expr

    typestr = typestr.strip()
    if string_str != None:
        string_str = string_str.strip()
    
    if not type(value) is gdb.Value:
        if typestr in py_string_types:
            return str(value)
        if typestr in py_int_types:
            return int(value)
        if typestr in py_float_types:
            return float(value)
        raise PrettyPromptException()

    if typestr != '':
        if typestr[0] == '(':
            if typestr[-1] != ')':
                raise PrettyPromptException()
            typename = typestr[1:-1]
        else:
            is_pointer = 0
            while typestr[0] == 'p':
                is_pointer += 1
                typestr = typestr[1:]
            if not typestr in known_types:
                raise PrettyPromptException()
            typename = known_types[typestr]
            while is_pointer > 0:
                is_pointer -= 1
                typename += '*'    
        gdb_type = janitor.typecache.cache.get_type(typename)
        if gdb_type == None:
            raise PrettyPromptException()
        value = value.cast(gdb_type)
    
    if string_str != None:
        if string_str == 's':
            value = value.string("iso-8859-1")
        elif string_str == 'e':
            value = janitor.dump.escape_string(value.string("iso-8859-1"))
        elif string_str == 't':
            dump = janitor.dump.Dump()
            value = dump.to_dump_string(value.string("iso-8859-1"))
        elif string_str == 'r':
            value = janitor.dump.remove_nonprintable(value.string("iso-8859-1"))
        else:
            raise PrettyPromptException()
    
    return value

def gdb_prompt_substitute(prompt):
    """Call extended prompt substitution from gdb.prompt module."""
    expanded = gdb.prompt.substitute_prompt(prompt)
    if expanded == None:
        return prompt
    else:
        return expanded

def find_separator(prompt, start, sep):
    """Find separator skipping parts enclosed in brackets."""
    level = 1
    length = len(prompt)
    while start < length:
        if start + 1 < length and prompt[start] == '\\':
            start += 1
        elif level == 1 and prompt[start] == sep:
            return start
        elif prompt[start] == '{':
            level += 1
        elif prompt[start] == '}':
            if level <= 1:
                return -1
            level -= 1
        start += 1
    return -1

def split_on_separator(prompt, sep):
    """Split string on first separator occurrence skipping parts enclosed in brackets."""
    
    colon_ptr = find_separator(prompt, 0, sep)
    if colon_ptr == -1:
        return (prompt, None)
    return (prompt[:colon_ptr], prompt[colon_ptr+1:])

def get_frame_number(frame):
    """Get frame number by calculating distance to newest frame."""
    
    num = 0
    newer = frame.newer()
    while newer != None:
        newer = newer.newer()
        num += 1
    return num

def to_string_or_report_error(value, expr):
    """Convert value to string or error description if conversion is impossible. 'None' is flattened to empty string."""
    
    if value == None:
        return False, ''
    
    try:
        result = str(value)
    except Exception as e:
        return True, "?{"+expr+"!"+str(e)+"}"
        
    return False, result

def to_string_or_error(value, expr):
    """Convert value to string or error description if conversion is impossible. 'None' is flattened to empty string."""
        
    return to_string_or_report_error(value, expr)[1]

def smart_bool(value):
    """Convert value to boolean. If it's string convertible to integer, convert it to integer first."""
    
    if type(value) is str or type(value) is unicode:
        if (value == "False"):
            return False
        
        try:
            value = int(value)
        except:
            pass
    
    try:
        return bool(value)
    except:
        return False

def is_none_or_empty(value):
    """Returns true is value is None or empty string."""
    
    # GDB doesn't like comparing gdb.Value with ''
    if type(value) is str or type(value) is unicode:
        return value == ''
    return value == None

def maybe_number(value):
    """If value is a string representing number, try to convert it to numeric type."""
    
    if (type(value) is str or type(value) is unicode) and len(value) != 0:
        try:
            # Check if first character after optional +/- is digit or .
            test_ptr = 0
            if value[0] == '-' or value[0] == '+':
                if len(value) == 1:
                    return value
                test_ptr = 1
            
            if not value[test_ptr].isdigit() and not value[test_ptr] == '.':
                return value
            
            # If there's '.', 'e' or 'E' in string, it can be only floating point (or not a valid number),
            # unless it's hex. Otherwise it can be only integer (or not a valid number)
            if (not '.' in value and not 'e' in value and not 'E' in value) or (value[0] == '0' and value[1].upper() == 'X'):
                return int(value, 0)
            else:
                return float(value)
        except:
            pass
    
    return value

def substitute_expression(expression, numbers = False):
    """Perform expression substitution."""

    # If it's escape sequence just substitute it without further constiderations
    if expression[0] == '[':
        err, expanded = to_string_or_report_error(substitute_value_prompt(expression[1:], numbers = False), expression[1:])
        if err:
            return "?{"+func+":"+expanded+"}"
        return janitor.ansiterm.term.wrap_sgr_seq(expanded)
    
    # Split function and arguments
    func, args = split_on_separator(expression, ':')
    if args == None:
        if func != "fn" and func != "tn" and (len(func) != 1 or not func in "fnt"):
            return "?${"+expression+"}"
        # 'fn', 'tn', 'f', 'n' and 't' functions can be called without arguments
        args = ""
    else:
        if func == "fn" or func == "tn":
            return "?${"+expression+"}"

    # Check if there is more than one argument
    args, args_right = split_on_separator(args, ':')

    if len(func) > 0 and func[0] == '?':
        if args_right != None:
            # Make sure there are no more than two arguments
            args_right, extra = split_on_separator(args_right, ':')
            if extra != None:
                return "?${"+func+":"+args+":"+args_right+"?:"+extra+"}"
            
            # Extract cast and format specifiers from second argument
            args_right, format_right = split_on_separator(args_right, '|')
            args_right, castexpr_right = split_on_separator(args_right, '#')
        else:
            args_right, format_right, castexpr_right = '', None, None
    elif args_right != None:
        # Only one argument expected. Report error if two colons found
        return "?${"+func+":"+args+"?:"+args_right+"}"
    
    # Extract cast and format specifiers from first argument
    args, format = split_on_separator(args, '|')
    args, castexpr = split_on_separator(args, '#')

    if func == '':
        # Concatenation or formatting
        result = substitute_value_prompt(args, numbers = False)
    
    elif func == 'g':
        # GDB evaluation
        # Expand argument, prefer strings
        err, expanded = to_string_or_report_error(substitute_value_prompt(args, numbers = False), args)
        if err:
            return "?{"+func+":"+expanded+"}"
        try:
            result = gdb.parse_and_eval(expanded)
        except Exception as e:
            return "?{"+func+":?"+expanded+"!"+str(e)+"}"
    
    elif func == 'e':
        # Python evaluation
        # Actual evaluation is done in substitute_value_prompt. Why not here? I don't remember.
        try:
            result = substitute_value_prompt(args, numbers = True, evaluate = True)
        except Exception as e:
            return "?{"+func+":?"+args+"!"+str(e)+"}"
    
    elif func == 'p':
        # GDB parameter
        err, attr = to_string_or_report_error(substitute_value_prompt(args, numbers = False), args)
        if err:
            return "?{"+func+":?"+attr+"}"
        try:
            result = gdb.parameter(attr)
        except Exception as e:
            return "?{"+func+":?"+args+"!"+str(e)+"}"
    
    elif func in ( 'f', 'v', 'r', 'fn', 'n', 'nv', 'nr' ):
        # Register, variable or frame attribute
        # Expand argument, prefer strings
        err, attr = to_string_or_report_error(substitute_value_prompt(args, numbers = False), args)
        if err:
            return "?{"+func+":"+attr+"}"
        try:
            # No frame if no thread
            thread = gdb.selected_thread()
            if thread == None or not thread.is_valid():
                if (attr != 'is_valid' and attr != '') or func == 'fn':
                    return None
                else:
                    return False
            
            # Pick frame, either selected or newest
            # If selected frame is invalid, gdb may still coredump here - at least the one I use - 7.11.1 on mingw64
            frame = (gdb.selected_frame() if func[0] != 'n' else gdb.newest_frame())
            if frame == None or not frame.is_valid():
                if func != 'f' and func != 'n' or attr != 'is_valid' and attr != '':
                    return None
                else:
                    return False
            
            if func == 'v' or func == 'nv':
                # Read variable
                try:
                    result = frame.read_var(attr)
                except:
                    result = None
            elif func == 'r' or func == 'nr':
                # Read register
                try:
                    result = frame.read_register(attr)
                except Exception as e:
                    return "?{"+func+":?"+attr+"!"+str(e)+"}"
            elif attr == 'num' or func == 'fn':
                # Calculate frame number
                try:
                    result = get_frame_number(frame)
                except:
                    result = None
            elif attr != 'select' and hasattr(frame, attr):
                # Get frame object attribute or function. The 'select' function is not allowed
                try:
                    result = getattr(frame, attr)
                    if callable(result):
                        result = result()
                except Exception as e:
                    return "?{"+func+":?"+attr+"!"+str(e)+"}"
            elif attr == "":
                result = True
            else:
                # Invalid attribute
                return "?{"+func+":?"+attr+"}"
        except:
            result = None
    
    elif func == 't' or func == 'tn':
        # Thread attribute
        # Expand argument, prefer strings
        err, attr = to_string_or_report_error(substitute_value_prompt(args, numbers = False), args)
        if err:
            return "?{"+func+":"+attr+"}"
        try:
            # Operate on selected thread
            thread = gdb.selected_thread()
            if thread == None or not thread.is_valid():
                if func == 'tn' or (attr != 'is_valid' and attr != ''):
                    return None
                else:
                    return False
            
            if func == 'tn':
                attr = 'num';
            
            if attr == 'pid' or attr == 'lwpid' or attr == 'tid':
                try:
                    # Pick correct field from 'ptid' triad
                    ptid = thread.ptid
                    if attr == 'pid':
                        result = ptid[0]
                    elif attr == 'lwpid':
                        result = ptid[1]
                    else:
                        result = ptid[2]
                except Exception as e:
                    return "?{"+func+":?"+attr+"!"+str(e)+"}"
            elif attr != 'switch' and hasattr(thread, attr):
                # Get thread object attribute or function. The 'switch' function is not allowed
                try:
                    result = getattr(thread, attr)
                    if callable(result):
                        result = result()
                except Exception as e:
                    return "?{"+func+":?"+attr+"!"+str(e)+"}"
            elif attr == "":
                result = True
            else:
                # Invalid attribute
                return "?{"+func+":?"+attr+"}"
        except:
            result = None
    elif func[0] == '?':
        # 'if true / else', 'if not empty / else' function
        expr = func[1:]
        if len(expr) != 0:
            try:
                # Expand and python-evaluate conditional expression
                expanded = substitute_value_prompt(expr, numbers = True, evaluate = True)
            except Exception as e:
                if args_right != '':
                    args += ":" + args_right;
                return "?{?"+func+":"+args+"!"+str(e)+"}"
            if not smart_bool(expanded):
                # 'false' - select 'else' part
                args, format, castexpr = args_right, format_right, castexpr_right
            # Expand 'if true' or 'else' part
            result = substitute_value_prompt(args, numbers = numbers)
        else:
            # Expand 'if not empty' part
            result = substitute_value_prompt(args, numbers = numbers)
            if is_none_or_empty(result):
                # Substitute with 'else' part
                result = substitute_value_prompt(args_right, numbers = numbers)
                format = format_right
                castexpr = castexpr_right
    else:
        return "?${?" + func + ":" + args + "}"
        
    # Cast expression if type specified
    if not is_none_or_empty(result) and castexpr != None:
        err, castexpr = to_string_or_report_error(substitute_value_prompt(castexpr, numbers = False), castexpr)
        if err:
            return "?{" + func + ":" + args + "#?" + castexpr + "}"
        try:
            result = try_cast(result, castexpr)
        except Exception as e:
            result = "?{" + func + ":" + args + "#?" + castexpr
            if str(e) != '':
                result += "!" + str(e)
            result += "}"
    
    # Format result if not empty and formatting specified
    if not is_none_or_empty(result) and format != None:
        format = str(gdb_prompt_substitute(format))
        try:
            result = format % result
        except Exception as e:
            result = "?${" + func + ":" + args + "|?" + format + "!" + str(e) + "}"
    
    return result

def substitute_value_prompt(prompt, numbers = False, evaluate = False):
    """Perform value substitutions and optional Python evaluation on PROMPT."""
    
    global __builtins__
    
    res = []
    parts = []
    
    if evaluate:
        arg = []
        expr_globals = {
            '__builtins__': __builtins__,
            'gdb' : gdb,
            'arg': arg
        }
    
    # Argument number for python evaluation
    arg_number = 0

    # Previously evaluated expression, for error reporting
    prev_part = None

    # Input prompt length
    prompt_len = len(prompt)
    # Number of input characters substituted so far
    prompt_part_start = 0
    prompt_ptr = 0

    # Need at least two characters to react
    # ignore closing \ and $
    while prompt_ptr < prompt_len - 1:
        # Ignore character after '\'
        if prompt[prompt_ptr] == '\\':
            prompt_ptr += 2
            continue
        # Continue if no substitution here
        if prompt[prompt_ptr] != '$' or prompt[prompt_ptr+1] != '{':
            prompt_ptr += 1
            continue
        
        # Find matching '}'
        ket = find_separator(prompt, prompt_ptr+2, '}')
        
        # Ignore if no closing bracket
        if ket == -1:
            prompt_ptr += 2
            continue
        
        # Expand part before $ with gdb.prompt
        if prompt_ptr != prompt_part_start:
            prompt_part = prompt[prompt_part_start : prompt_ptr]
            expanded = gdb_prompt_substitute(prompt_part)
            
            res.append(expanded)
        
        # Expand expression
        prompt_part = prompt[prompt_ptr + 2 : ket]
        expanded = substitute_expression(prompt_part, numbers)
        if evaluate:
            arg.append(expanded)
            res += ( "arg[", str(arg_number), "]")
            arg_number += 1
        else:
            res.append( ( expanded, prompt_part ) )

        prompt_part_start = ket + 1
        prompt_ptr = prompt_part_start
    
    # Expand last (or only) part with gdb.prompt
    if prompt_len != prompt_part_start:
        prompt_part = prompt[prompt_part_start : ]
        expanded = gdb_prompt_substitute(prompt_part)
        
        # If there are no substitutions and numbers are allowed, try to convert result to numeric value
        # There are reasons why it is not done is substitutions are present, but I don't remember what reasons,
        # something with numbers being treated as octals.
        if len(res) == 0 and numbers:
            res.append(maybe_number(expanded))
        else:
            res.append(expanded)
    
    if len(res) > 1 or evaluate:
        # Convert parts to strings and join
        output_prompt = ''.join([to_string_or_error(part[0], part[1]) if type(part) is tuple else part for part in res])
    elif len(res) == 1:
        # Return as is
        res = res[0]
        output_prompt = res[0] if type(res) is tuple else res
    else:
        output_prompt = None
    
    if evaluate:
        if is_none_or_empty(output_prompt):
            return None
        
        output_prompt = eval(output_prompt, expr_globals)
    
    return output_prompt

def substitute_value_prompt_str(prompt):
    """Perform value substitutions and convert result to string."""
    result = substitute_value_prompt(prompt, numbers = False, evaluate = False)
    result = to_string_or_error(result, prompt)
    return result;

