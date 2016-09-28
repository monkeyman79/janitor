
if ! $janitor_alias_set
  alias jau = janitor disassemble
  alias jad = janitor dump
  alias jar = info janitor registers
  alias jaf = info janitor cpu-flags
  alias jas = janitor raw-stack
  set $janitor_alias_set = 1
end

define i8086
  set arch i8086
  set disassembly-flavor intel
  set janitor i8086 on
  set janitor word-width 2
end

define i386
  set arch i386
  set disassembly-flavor intel
  set janitor i8086 off
  set janitor word-width 4
end

set janitor registers-save on
set janitor registers-on-stop on
set janitor disassemble-next-instr on

set janitor prompt ${?${tn}:${[33}*${tn}${[} }${?${fn}>0:\#${fn} }${?${f}:${[36}${?${p:arch}=="i8086":${r:cs|%04X}\:${f:pc|%04X}:${f:pc|%08X}}:${[33}gdb}${[}-> 
