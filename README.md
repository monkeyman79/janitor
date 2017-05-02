# janitor
Collection of GDB commands for low-level debugging, aimed at bringing debug.exe flavor into GDB command line interface.
It includes advanced prompt substitution functionality.

## Screenshot
![ScreenShot](https://cloud.githubusercontent.com/assets/22123431/18913270/440aceb6-8587-11e6-97d1-fed40ce9f4ce.png)

## Install

* Clone repository
```bash
~/git$ git clone https://github.com/monkeyman79/janitor.git
```

* Add following line to your `~/.gdbinit`
```
source ~/git/janitor/.gdbinit
```

* If you cloned the repository in some other location, modify `janitor/.gdbinit`

* Modify `janitor.gdb` to your taste

## Start

To install aliases, enable all features and setup fancy prompt, just type start-janitor in gdb command line.

## Commands
#### Quick list
    info janitor registers (alias jar)
    info janitor cpu-flags (alias jaf)
    set janitor registers-save on|off
    show janitor registers-save
    set janitor registers-on-stop on|off
    show janitor registers-on-stop
    janitor disassemble [start] [,end | ,+length] (alias jau)
    set janitor disassemble-next-instr on|off
    show janitor disassemble-next-instr
    janitor dump [/fmt] [start] [,end | ,+length] (alias jad)
    janitor raw-stack [/fmt] [+length] (alias jas)
    set janitor word-width 2|4
    show janitor word-width
    set janitor dump-line-align on|off
    show janitor dump-line-align
    set janitor prompt PROMPT
    janitor eval PROMPT
    set janitor ansi on|off
    set janitor i8086 on|off

### Registers
##### `info janitor registers`
##### alias `jar`
Display CPU registers in low-lever debugger style with colors. At this moment the command support only i386 and ARM architectures.

##### `info janitor cpu-flags`
##### alias `jaf`
Display detailed `eflags` register contents.

##### `set janitor registers-save on|off`
##### `show janitor registers-save`
If this option is enabled, registers which have changed in last execution step are highlighted.

##### `set janitor registers-on-stop on|off`
##### `show janitor registers-on-stop`
If this option is enabled, registers are displayed after each execution step.

### Disassemble
##### `janitor disassemble [start] [,end | ,+length]`
##### alias `jau`
Disassemble in low-level debugger style with colors. If `start` parameter is not specified, this command will continue disassembling at the point where it was previously finished.
##### `set janitor disassemble-next-instr on|off`
##### `show janitor disassemble-next-instr`
If this option is enabled, janitor will display disassembly of next instruction when execution stops.

### Dump
##### `janitor dump [/fmt] [start] [,end | ,+length]`
##### alias `jad`
Dump memory in low-lever debugger style with colors.

The optional `fmt` parameter consists of size and endianness letters.
Size letters are:
* `1`/`b` - byte (default)
* `2`/`h`/`s` - 2 bytes
* `4`/`d`/`l` - 4 bytes
* `8`/`g`/`q` - 8 bytes
* `w` - configured word size.

Endianness letters are
* `l` - little endian
* `b` - big endian.

Order of size and endianness letters is not significant, `b` and `l` are interpreted as endianness letters only if accompanied with size letter.

If the `fmt` is not specified, format used in previous invocation will be used. If `start` is not specified, dump will continue at the point where it was previously finished.

##### `janitor raw-stack [/fmt] [+length]`
##### alias `jas`
Dump stack memory, similar to `janitor dump $sp`. Word width configured with `set janitor word-width` is used unless width is explicitly specified. It will try to highlight current stack frame in dumped bytes.

##### `set janitor word-width 2|4`
##### `show janitor word-width`
Default word width used for `janitor raw-stack` command by default, and for `janitor dump` command when `w` is present in `fmt` parameter.

##### `set janitor dump-line-align on|off`
##### `show janitor dump-line-align`
When this parameter is enabled, lines of memory dump will always begin at addresses being multiple of 16.

### Prompt
##### `set janitor prompt `*`PROMPT`*
Set advanced prompt substitution string. Substitutions are described in separate paragraph below.
##### `janitor eval `*`PROMPT`*
Evaluate and display advanced prompt without changing the actual prompt.

### ANSI terminal
##### `set janitor ansi on|off`
If this option is disabled, janitor doesn't use any ANSI terminal sequence in registers display, dump or disassembly, just raw text. For those poor souls who don't have ansi terminal.

### Miscellaneous
##### `set janitor i8086 on|off`
Enables i8086 hack to disassemble by default starting at `$cs:$eip` instead or `$pc` and dump stack from `$ss:$esp` instead of `$sp`. This is useful when debugging real mode code e.g. running in QEMU. This should be somehow fixed in GDB, but that's completely different story.

## Advanced prompt substitution
All substitutions are enclosed between `${` and `}`. Substitutions can be nested. Use backslash to escape characters from special interpretation: `\$`, `\{`, `\}`, `\:`, `\#`, `\|`.

### Substitutions
#### Frames, registers and variables
##### `${r:reg}`
Value of register in selected frame.

##### `${v:var}`
Value of variable in selected frame.

##### `${fn}`
Selected frame number

##### `${f[:attr]}`
Selected frame attribute. Frame attribute can be one of: `is_valid`, `num`, `name`, `architecture`, `pc`, `type`, `unwind_stop_reason`. Default attribute is `is_valid`

##### `${nr:reg}`
Value of register in newest frame.

##### `${nv:var}`
Value of variable in newest frame.

##### `${n[:attr]}`
Newest frame attribute.

#### Threads
##### `${tn}`
Selected thread number

##### `${t:[attr]}`
Selected thread attribute. Thread attribute can be one of: `is_valid`, `num`, `name`, `global_num`, `pid`, `lwpid`, `tid`, `is_stopped`, `is_running`, `is_exited`. Default is `is_valid`

#### GDB paremeters
##### `${p:param}`
Value of GDB parameter

#### ANSI SGI sequences
##### `${[SEQ}`
If ANSI sequences are enabled, evaluates to ANSI escape sequence `\e[SEQm`. Otherwise evaluates to empty string

#### Expressions and conditionals
##### `${g:exp}`
Expression value evaluated by GDB. Substitutions are converted to strings before evaluation.

##### `${e:exp}`
Expression value evaluated by Python. Substitutions are passed as variables to evaluation.

##### `${?subst:if_true[:if_false]}`
Substitute `if_true` if `subst` evaluates to true, otherwise substitute `if_false`.
The `subst` expression undergoes substitution and is then evaluated by Python.

Inside `{?subst:true:false}`, each of `true` and `false` can be followed by a format or cast specifier
(ie. terminating `|format` applies to `false` part only).
To apply format to both parts, use `{:{?subst:true:false}|format}`.

##### `${?:subst[:if_false]}`
Substitute `subst` if it is anything different than None and empty string, otherwise substitute `if_false`.

##### `${:exps}`
Concatenation, evaluates and concatenates expressions. Can be also used to apply formatting.

### Formatting
Append `|format` inside substitution brackets to format resulting value.

### Type casting
Append `#type[%string_conversion]` inside substitution brackets to cast resulting value. Cast operation works differently for values of type gdb.Value and for all other types.
    
For gdb values it is possible to cast to any known type, using `#(full type name)` or use abbreviations for some well known types:
* `[s|u]c`   - `[signed|unsigned] char`
* `[u]s`     - `[unsigned] short`
* `[u]i`     - `[unsigned] int`
* `[u]l`     - `[unsigned] long`
* `[u]ll`    - `[unsigned] long long`
* `f`        - `float`
* `d`        - `double`
* `ld`       - `long double`
* `func`     - `void ()`
Prepend 'p' before abbreviation to turn it into pointer to given type.

For non-gdb values reasonable casts are:
* `pc` -    Convert to string
* `i` -     Convert to integer value
* `f` -     Convert to floating point value

Optional `string_conversion` specifier applies only to values of type gdb.Value. Allowed values are:
* `s`  -    Call string() method on the value to convert it to Python string
* `e`  -    Convert to Python string and escape non-printable characters with C escape sequences
* `r`  -    Convert to Python string and remove non-printable characters
* `t`  -    Insert ANSI term sequences to produce result as displayed by `janitor dump` command

### Inherited from extended-prompt
Apart from `${`  `}` substitutions, backslash substitutions from extended-prompt apply:

*  `\[`    Begins a sequence of non-printing characters.
*  `\\`    A backslash.
*  `\]`    Ends a sequence of non-printing characters.
*  `\e`    The ESC character.
*  `\f`    The selected frame; an argument names a frame parameter.
*  `\n`    A newline.
*  `\p`    A parameter's value; the argument names the parameter.
*  `\r`    A carriage return.
*  `\t`    The selected thread; an argument names a thread parameter.
*  `\v`    The version of GDB.
*  `\w`    The current working directory.
  
### Examples

`${?${fn}!=0:[${fn}]}` - Expands to frame number enclosed in square brackets if selected frame is not top frame.

`${?${r:cs}==${nr:cs}:cs:${r:cs|%08X}}`  - Expands to string **cs** if value of `cs` register in selected frame is the same as the register's value in top frame. Otherwise it expands to value of `cs` register formated as hexadecimal number.

## Acknowlegements

Layout of displayed registers and general colors arrangement has been almost verbatim copied from [GRDB Debugger by LADSoft](http://ladsoft.tripod.com/grdb_debugger.html).
