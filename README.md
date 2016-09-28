# janitor
Collection on GDB commands useful for low-level debugging, aimed at bringing debug.exe flavor into GDB command line interface.
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

## Commands
### Registers
#### `info janitor registers`
##### alias `jar`
Display CPU registers in low-lever debugger style with colors. At this moment the command support only i386 architecture.

#### `info janitor cpu-flags`
##### alias `jaf`
Display detailed `eflags` register contents.

#### `set janitor registers-save on|off`
#### `show janitor registers-save`
If this option is enabled, registers which have changed in last execution step are highlighted.

#### `set janitor registers-on-stop on|off`
#### `show janitor registers-on-stop`
If this option is enabled, registers are displayed after each execution step.

### Disassemble
#### `janitor disassemble [start] [,end | ,+length]`
##### alias `jau`
Disassemble in low-level debugger style with colors. If `start` parameter is not specified, this command will continue disassembling at the point where it was previously finished.
#### `set janitor disassemble-next-instr on|off`
#### `show janitor disassemble-next-instr`
If this option is enabled, janitor will display disassembly of next instruction when execution stops.

### Dump
#### `janitor dump [/fmt] [start] [,end | ,+length]`
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

Order of size and endianness letter is not significant, `b` and `l` are interpreted as endianness letters only if accompanied with size letter.

If the `fmt` is not specified, format used in previous invocation will be used. If `start` is not specified, dump will continue at the point where it was previously finished.

#### `janitor raw-stack [/fmt] [+length]`
##### alias `jas`
Dump stack memory, similar to `janitor dump $sp`. Word width configured with `set janitor word-width` is used, unless width is explicitly specified. It will try to highlight current stack frame in dumped bytes.

#### `set janitor word-width 2|4`
#### `show janitor word-width`
Default word width used for `janitor raw-stack` command by default, and for `janitor dump` command when `w` is present in `fmt` parameter.

#### `set janitor dump-line-align on|off`
#### `show janitor dump-line-align`
When this parameter is enabled, lines of memory dump will always begin at addresses being multiple of 16.

### Prompt
#### `set janitor prompt `*`VALUE`*
Set advanced prompt substitution string. Substitutions are described in separate paragraph below.
#### `janitor eval `*`VALUE`*
Evaluate and display advanced prompt without changing the actual prompt.

### ANSI terminal
#### `set janitor ansi on|off`
If this option is disabled, janitor doesn't use any ANSI terminal sequence in registers display, dump or disassembly, just raw text. For those poor souls who don't have ansi terminal.

### Miscellaneous
#### `set janitor i8086 on|off`
Enables i8086 hack to disassemble by default starting at `$cs:$eip` instead or `$pc` and dump stack from `$ss:$esp` instead of `$sp`. This is useful when debugging real mode code e.g. running in QEMU. This should be somehow fixed in GDB, but that's completely different story.


