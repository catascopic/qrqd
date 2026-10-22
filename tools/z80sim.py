"""Runs a compiled TI-83+ assembly program (.8xp) in a Z80 emulator, for the tests.

AsmMachine has the interface of axesim's Machine (set_real, get_real, set_str, set_list, run,
ans, displays, os, mem, full), so the engine tests can run the Z80 port of prgmθQR
(docs/asm_port.md), the release's engine, rather than an Axe source. The CPU is the `z80` package
(Ivan Kosarev's emulator, C++ core). What the calculator's OS does is modelled here:

- Memory: the TI-83+ RAM map. The program's code is copied to userMem (9D95h), as Asm( does.
  Writes are allowed only to the scratch areas (saveSScreen = L₁, plotSScreen = the graph
  buffer, appBackUpScreen = L₃), OP1-OP6, the program itself, the stack below the return
  address, and the data of OS variables in RAM. Anything else (ROM, the OS's RAM, the VAT,
  the caller's stack) raises.
- OS variables: their data in RAM from C000h, and a real VAT, built when the program starts:
  the symbol table (reals, strings: fixed 3-byte names) from symTable (FE66h) down, then the
  program table (lists, appvars, programs: a length byte and the name) from (progPtr) down to
  (pTemp). `add_appvar` and `add_vat_other` add appvars (notes) and other entries, as in
  axesim.
- Archive: flash pages of 16 KB (`flash`, page -> bytes), read through port 6 (bank A: the
  page written there shows at 4000h-7FFFh, which is how the engine and Axe read archived
  data) or with `_LoadCIndPaged` (the byte at page B, address HL in 4000h-7FFFh). Bank A
  starts with an OS page (`OS_PAGE`) that holds no archive, so a read there before mapping
  an archive page raises, as does a jump there or a write. An archived variable is an entry there, as the OS
  writes it: FCh (valid), the size of the rest (word), a copy of its VAT entry going up (type,
  T2, version, address low, high, page), the name length and the name, then the data (for an
  appvar: size word, content). Its VAT entry, and so `_ChkFindSym`, gives the page (B) and the
  address of the FCh byte (DE). The archive starts 16 bytes before the end of page 0Bh, so
  every archived variable's entry crosses a page boundary somewhere in the tests.
- OS calls: bcall (rst 28h) runs a Python version of the routine; only those in BCALLS exist
  (`_GrBufCpy`, the display, records the graph buffer in `displays`, as axesim's DispGraph does;
  `_MemChk` reports `free_ram`; `_DelVarArc` deletes what `_ChkFindSym` found; `_CreateStrng`
  makes a string in RAM, and raises if one of that name exists or RAM is short),
  any other raises. After one, every register it doesn't return is set to junk (5A5Ah), the
  shadow registers too, so the program can't count on the OS keeping a value. ROM is filled
  with FFh (rst 38h), so a jump into ROM stops at 0038h and raises instead of running.
- Interrupts: none are generated (the emulator raises none by itself), but the shadow
  registers are set to junk every 100,000 T-states, as the OS's interrupt handler would
  change them (assumed: it uses exx and ex af,af').
- Ports: port 2 reads the model (bit 7 set on a TI-84+ or Silver Edition); port 20h (CPU
  speed) can be written on those only; port 6 (bank A's page) can be read and written. Any
  other port raises.
- The final ret must come back to the pushed return address with the stack where it started,
  IY (the OS flags pointer) unchanged, interrupts still enabled and the OS's page back in
  bank A (the OS may be running code there when the program returns).

build.py writes the program's labels next to the .8xp (`_theta_QR.lab`); with them,
`call('FloatToInt', de=...)` runs one subroutine, like axesim's call(), under the same checks.
"""
from decimal import Decimal
from pathlib import Path

import z80

from axesim import Machine as AxeMachine     # for reading 9-byte floats back

USERMEM = 0x9D95
OP1, OP2 = 0x8478, 0x8483    # OP1-OP6: 6 registers of 11 bytes
FLAGS = 0x89F0               # IY points here while the OS runs
L1, L3, L6 = 0x86EC, 0x9872, 0x9340   # saveSScreen, appBackUpScreen, plotSScreen (768 bytes each)
STACK_LOW = 0xFE70           # the OS stack: 400 bytes below FFFFh
EXIT = 0x0040                # return address pushed for the program: reaching it ends the run
RET_SLOT = 0xFFDE            # where that return address sits (above it: the OS's own stack)
VAR_DATA = 0xC000            # where the harness puts OS variables' data
ARCH_PAGE, ARCH_START = 0x0B, 0x3FF0   # where the archive's entries start: page, offset in it
OS_PAGE = 0x03               # bank A's page when the program starts: an OS page, no archive on it
SYMTABLE, PROGPTR, PTEMP = 0xFE66, 0x9830, 0x982E
BCALL, RST38 = 0x0028, 0x0038
JUNK = 0x5A5A

REAL, LIST, STRING, PROG, PROTPROG, CLIST, APPVAR = 0x00, 0x01, 0x04, 0x05, 0x06, 0x0D, 0x15
PROG_TABLE = {LIST, PROG, PROTPROG, APPVAR, CLIST, 0x16, 0x17}  # types with variable-length names

BCALLS = {0x41BF: '_OP1Set0', 0x4ABF: '_StoAns', 0x42F1: '_ChkFindSym',
          0x4792: '_SetXXXXOP2', 0x4156: '_OP2ToOP1', 0x486A: '_GrBufCpy',
          0x501D: '_LoadCIndPaged', 0x42E5: '_MemChk', 0x4FC6: '_DelVarArc',
          0x4327: '_CreateStrng'}
VAR_OVERHEAD = 11            # RAM a new string costs besides its text: size word + 9-byte VAT entry


class Z80Error(Exception):
    pass


def tifloat(v):
    """A number as the OS's 9-byte float: sign byte, exponent 80h+e, 14 BCD digits."""
    d = Decimal(str(v))
    if d == 0:
        return bytes([0, 0x80] + [0] * 7)
    sign, digits, exp = d.normalize().as_tuple()
    e = len(digits) - 1 + exp
    if not -99 <= e <= 99:
        raise Z80Error('%s is out of the calculator\'s range' % v)
    s = ''.join(map(str, digits)).ljust(14, '0')[:14]
    return bytes([0x80 if sign else 0, 0x80 + e]) + bytes(int(s[k]) * 16 + int(s[k + 1]) for k in range(0, 14, 2))


class AsmMachine:
    tifloat = staticmethod(tifloat)
    untifloat = staticmethod(AxeMachine.untifloat)

    def __init__(self, program, model='84+', max_ticks=1_500_000_000):
        """program: a .8xp path, or the program's bytes (BB 6D, then the code). model: '83+'
        (6 MHz only) or '84+' (has 15 MHz). max_ticks: T-states before the run is stopped as
        a hang (1.5e9 is 100 s at 15 MHz)."""
        self.labels = {}            # NAME -> address, from the .lab build.py writes next to the .8xp
        if isinstance(program, (str, Path)):
            from tivars import TIEntry
            lab = Path(program).with_suffix('.lab')
            if lab.exists():
                for line in lab.read_text(encoding='ascii').splitlines():
                    name, value = line.split(' = ')
                    self.labels[name] = int(value.lstrip('$'), 16)
            program = bytes(TIEntry.open(str(program)).data)
        if program[:2] != b'\xbb\x6d':
            raise Z80Error('not a compiled assembly program (no BB 6D)')
        self.code = bytes(program[2:])
        if USERMEM + len(self.code) > 0xC000:
            raise Z80Error('code runs past C000h (%d bytes)' % len(self.code))
        self.model = model
        self.max_ticks = max_ticks
        self.ans = None
        self.full = False           # 15 MHz set (port 20h bit 0) when the program returned
        self.displays = []          # the graph buffer at each display call
        self.calls = []             # names of the OS routines called, in order
        self.os = {}                # (kind, name) -> pointer to the data, as in axesim (RAM only)
        self.vars = {}              # (kind, name) -> (type, VAT name bytes, data pointer, page)
        self.ticks = 0              # T-states the last run took
        self.free_ram = 20000       # what _MemChk reports; _CreateStrng needs size + 11 of it
        self.cpu = z80.Z80Machine()
        self.mem = self.cpu.memory
        self.mem[0:0x8000] = b'\xff' * 0x8000
        self.cpu.set_memory_block(USERMEM, self.code)
        self.var_ptr = VAR_DATA
        self.flash = {}             # flash page -> bytearray(16384), the archive
        self.arch_page, self.arch_off = ARCH_PAGE, ARCH_START
        self.bank_a = OS_PAGE       # port 6: the flash page seen at 4000h-7FFFh
        # every address is write-protected, then the allowed areas are opened
        self.cpu.set_write_callback(self._bad_write)
        self.cpu.mark_addrs(0, 0x10000, self.cpu.WRITE_MARK)
        # 4000h-7FFFh shows the archive page in bank A (port 6); a read with the OS's page
        # there, or running code there, is a bug
        self.cpu.set_read_callback(self._read_bank_a)
        self.cpu.mark_addrs(0x4000, 0x4000, self.cpu.READ_MARK)
        for start, size in ((OP1, 66), (L1, 768), (L6, 768), (L3, 768),
                            (USERMEM, len(self.code)), (STACK_LOW, RET_SLOT - STACK_LOW)):
            self.writable(start, size)
        self.cpu.set_input_callback(self._port_in)
        self.cpu.set_output_callback(self._port_out)
        self.cpu.set_breakpoint(BCALL)
        self.cpu.set_breakpoint(RST38)
        self.cpu.set_breakpoint(EXIT)

    def writable(self, start, size):
        self.cpu.unmark_addrs(start, size, self.cpu.WRITE_MARK)

    def _bad_write(self, addr, value):
        raise Z80Error('write of %02Xh to %04Xh (PC %04Xh)' % (value, addr, self.cpu.pc))

    def _read_bank_a(self, addr):
        if addr == self.cpu.pc:
            raise Z80Error('ran into %04Xh, outside the program' % addr)
        if self.bank_a not in self.flash:
            raise Z80Error('read from %04Xh (PC %04Xh) with page %02Xh in bank A, which holds no '
                           'archive: map an archive page through port 6 first'
                           % (addr, self.cpu.pc, self.bank_a))
        return self.flash[self.bank_a][addr - 0x4000]

    # ---------- ports ----------
    def _port_in(self, port):
        port &= 0xFF
        if port == 2:
            return 0x80 if self.model == '84+' else 0x00
        if port == 6:
            return self.bank_a
        raise Z80Error('in from port %02Xh (PC %04Xh)' % (port, self.cpu.pc))

    def _port_out(self, port, value):
        port &= 0xFF
        if port == 0x20 and self.model == '84+':
            self.full = bool(value & 1)
            return
        if port == 6:
            self.bank_a = value
            return
        raise Z80Error('out %02Xh to port %02Xh on a %s (PC %04Xh)' % (value, port, self.model, self.cpu.pc))

    # ---------- OS variables ----------
    def _add_var(self, key, typ, name, data, archived):
        """Store a variable's data (RAM, or an entry in the archive) and remember its VAT entry."""
        if archived:
            p, page = self._archive(typ, name, data)
            self.os.pop(key, None)
        else:
            p, page = self.var_ptr, 0
            self.mem[p:p + len(data)] = data
            self.writable(p, len(data))
            self.var_ptr += len(data) + 16
        self.vars[key] = (typ, name, p, page)
        return p

    def _archive(self, typ, name, data):
        """Write an archive entry (see the module's notes) at the archive's end, crossing into
        the next page where it must; return (address of its FCh byte, page)."""
        page, off = self.arch_page, self.arch_off
        head = bytes([typ, 0, 0, (0x4000 + off) & 0xFF, (0x4000 + off) >> 8, page, len(name)])
        rest = head + name + data
        entry = bytes([0xFC]) + len(rest).to_bytes(2, 'little') + rest
        for b in entry:
            self.flash.setdefault(self.arch_page, bytearray([0xFF] * 0x4000))[self.arch_off] = b
            self.arch_off += 1
            if self.arch_off == 0x4000:
                self.arch_page, self.arch_off = self.arch_page + 1, 0
        return 0x4000 + off, page

    def flash_read(self, page, addr):
        """The archive byte at page, address (4000h-7FFFh), as _LoadCIndPaged reads it."""
        if not 0x4000 <= addr < 0x8000:
            raise Z80Error('flash read at %04Xh, outside 4000h-7FFFh' % addr)
        if page not in self.flash:
            raise Z80Error('flash read from page %02Xh, which holds no archived variables' % page)
        return self.flash[page][addr - 0x4000]

    def add_appvar(self, name, content, archived=False):
        """An appvar (a note, for example): its data is a size word, then content."""
        data = len(content).to_bytes(2, 'little') + bytes(content)
        p = self._add_var(('appvar', name), APPVAR, name.encode('latin-1'), data, archived)
        if not archived:
            self.os[('appvar', name)] = p + 2

    def _delete(self, entry):
        """_DelVarArc: delete the variable whose VAT entry is at `entry` (RAM or archive); the
        VAT closes up (build_vat again), as the OS's does."""
        found = [(typ, ptr, page) for e, typ, name, ptr, page in self.vat_entries() if e == entry]
        for key, (typ, name, ptr, page) in list(self.vars.items()):
            if found and (typ, ptr, page) == found[0] and ptr:
                del self.vars[key]
                self.os.pop(key, None)
                self.build_vat()
                return
        raise Z80Error('_DelVarArc: no variable has its VAT entry at %04Xh' % entry)

    def _create_string(self, size):
        """_CreateStrng: a new string named in OP1 (04h, AAh, number), `size` bytes, in RAM.
        Raises if one of that name exists (the OS would make a second one) or if RAM is short
        (the OS would stop with ERR:MEMORY). Returns HL = its VAT entry, DE = its size word."""
        op1 = bytes(self.mem[OP1:OP1 + 3])
        if op1[:2] != b'\x04\xaa':
            raise Z80Error('_CreateStrng: OP1 is not a string name: %s' % op1.hex())
        n = op1[2] + 1 if op1[2] < 9 else 0
        if ('str', n) in self.vars:
            raise Z80Error('_CreateStrng: Str%d exists already (delete it first)' % n)
        if size + VAR_OVERHEAD > self.free_ram:
            raise Z80Error('_CreateStrng: ERR:MEMORY (%d bytes, %d free)' % (size, self.free_ram))
        self.free_ram -= size + VAR_OVERHEAD
        self.set_str(n, bytes(size))
        self.build_vat()
        p = self.os[('str', n)] - 2
        entry = next(e for e, typ, name, ptr, page in self.vat_entries() if ptr == p)
        return {'hl': entry, 'de': p}

    def add_vat_other(self, typ, name):
        """A VAT entry with no data the engine may read (a program, a list), like axesim's."""
        self.vars[('other', typ, name)] = (typ, name.encode('latin-1'), 0, 0)

    def set_real(self, name, v, archived=False):
        p = self._add_var(('real', name), REAL, name.encode('latin-1'), self.tifloat(v), archived)
        if not archived:
            self.os[('real', name)] = p

    def get_real(self, name):
        p = self.os[('real', name)]
        return self.untifloat(bytes(self.mem[p:p + 9]))

    def set_str(self, n, toks, archived=False):
        data = bytes(toks)
        p = self._add_var(('str', n), STRING, bytes([0xAA, n - 1 if n else 9]),
                          len(data).to_bytes(2, 'little') + data, archived)
        if not archived:
            self.os[('str', n)] = p + 2

    def set_list(self, name, values, archived=False):
        """A real list, or a complex one if any value is complex: type 0Dh, 18 bytes an element
        (the real part, then the imaginary part, each with 0Ch in its first byte)."""
        if any(isinstance(v, complex) for v in values):
            def part(x):
                f = self.tifloat(x)
                return bytes([f[0] | 0x0C]) + f[1:]
            typ, body = CLIST, b''.join(part(v.real) + part(v.imag) for v in map(complex, values))
        else:
            typ, body = LIST, b''.join(self.tifloat(v) for v in values)
        data = len(values).to_bytes(2, 'little') + body
        p = self._add_var(('list', name), typ, b'\x5d' + name.encode(), data, archived)
        if not archived:
            self.os[('list', name)] = p + 2

    def build_vat(self):
        """Write the VAT: the symbol table from symTable down (9-byte entries), then the
        program table from (progPtr) down to (pTemp). An entry, downwards from its type byte at
        P: type, T2, version, data pointer low, high, flash page (0 = RAM), then the name: 3
        bytes in the symbol table; a length byte and the name in the program table."""
        sym = [v for v in self.vars.values() if v[0] not in PROG_TABLE]
        prog = [v for v in self.vars.values() if v[0] in PROG_TABLE]
        p = SYMTABLE
        for typ, name, ptr, page in sym:
            self._vat_head(p, typ, ptr, page)
            for k, ch in enumerate(name.ljust(3, b'\0')):
                self.mem[p - 6 - k] = ch
            p -= 9
        self.mem[PROGPTR:PROGPTR + 2] = p.to_bytes(2, 'little')
        for typ, name, ptr, page in prog:
            self._vat_head(p, typ, ptr, page)
            self.mem[p - 6] = len(name)
            for k, ch in enumerate(name):
                self.mem[p - 7 - k] = ch
            p -= 7 + len(name)
        self.mem[PTEMP:PTEMP + 2] = p.to_bytes(2, 'little')
        if p < self.var_ptr:
            raise Z80Error('the VAT ran into the variables\' data')

    def _vat_head(self, p, typ, ptr, page):
        self.mem[p] = typ
        self.mem[p - 1] = 0                  # T2
        self.mem[p - 2] = 0                  # version
        self.mem[p - 3] = ptr & 0xFF
        self.mem[p - 4] = ptr >> 8
        self.mem[p - 5] = page

    def vat_entries(self):
        """Walk the VAT in memory: (address of the type byte, type, name, data pointer, page)."""
        out, p = [], SYMTABLE
        prog = int.from_bytes(self.mem[PROGPTR:PROGPTR + 2], 'little')
        while p > prog:
            out.append((p, self.mem[p], bytes(self.mem[p - 6 - k] for k in range(3)).rstrip(b'\0'),
                        self.mem[p - 3] | self.mem[p - 4] << 8, self.mem[p - 5]))
            p -= 9
        end = int.from_bytes(self.mem[PTEMP:PTEMP + 2], 'little')
        while p > end:
            n = self.mem[p - 6]
            out.append((p, self.mem[p], bytes(self.mem[p - 7 - k] for k in range(n)),
                        self.mem[p - 3] | self.mem[p - 4] << 8, self.mem[p - 5]))
            p -= 7 + n
        return out

    def rd(self, p):
        return self.mem[p]

    def rd16(self, p):
        return self.mem[p] | self.mem[p + 1] << 8

    # ---------- OS routines ----------
    def _chkfindsym(self):
        """Find the variable named in OP1 (type byte, then the name). Carry set if there is
        none; else HL = its VAT entry, DE = its data, B = its flash page (0 = RAM). The
        symbol table is searched by its 3 name bytes (a real and a complex of the same name
        can't both exist); the program table by name and kind (list, program or appvar)."""
        op1 = bytes(self.mem[OP1:OP1 + 9])
        typ = op1[0] & 0x1F
        prog_table = typ in PROG_TABLE or op1[1] == 0x5D
        kind = {PROG: PROG, PROTPROG: PROG, 0x16: PROG, 0x17: PROG, APPVAR: APPVAR}
        for p, etyp, name, ptr, page in self.vat_entries():
            in_prog = (etyp & 0x1F) in PROG_TABLE
            if in_prog != prog_table:
                continue
            if prog_table:
                want = op1[1:9].split(b'\0')[0]
                if name != want or kind.get(etyp & 0x1F, LIST) != kind.get(typ, LIST):
                    continue
            elif name != op1[1:4].rstrip(b'\0'):
                continue
            return {'hl': p, 'de': ptr, 'b': page, 'carry': False}
        return {'carry': True}

    def _bcall(self, addr):
        name = BCALLS.get(addr)
        if name is None:
            raise Z80Error('unknown bcall %04Xh' % addr)
        self.calls.append(name)
        cpu, out = self.cpu, {}
        if name == '_OP1Set0':
            self.mem[OP1:OP1 + 9] = self.tifloat(0)
        elif name == '_StoAns':
            self.ans = self.untifloat(bytes(self.mem[OP1:OP1 + 9]))
        elif name == '_SetXXXXOP2':
            self.mem[OP2:OP2 + 9] = self.tifloat(cpu.hl)
        elif name == '_OP2ToOP1':
            self.mem[OP1:OP1 + 11] = bytes(self.mem[OP2:OP2 + 11])
        elif name == '_ChkFindSym':
            out = self._chkfindsym()
        elif name == '_MemChk':             # HL = free RAM
            out = {'hl': min(self.free_ram, 0xFFFF)}
        elif name == '_DelVarArc':          # the variable _ChkFindSym found (its VAT entry at HL)
            self._delete(cpu.hl)
        elif name == '_CreateStrng':        # a string named in OP1, HL bytes: DE = its size word
            out = self._create_string(cpu.hl)
        elif name == '_LoadCIndPaged':      # C = the byte at page B, address HL
            out = {'c': self.flash_read(cpu.b, cpu.hl)}
        elif name == '_GrBufCpy':        # the graph buffer to the LCD: record what it shows
            self.displays.append(bytes(self.mem[L6:L6 + 768]))
        # every register the routine doesn't return is junk afterwards
        for reg in ('af', 'bc', 'de', 'hl', 'ix'):
            setattr(cpu, reg, JUNK)
        self._junk_shadows()
        if 'hl' in out:
            cpu.hl = out['hl']
        if 'de' in out:
            cpu.de = out['de']
        if 'b' in out:
            cpu.b = out['b']
        if 'c' in out:
            cpu.c = out['c']
        if 'carry' in out:
            cpu.f = (cpu.f & 0xFE) | out['carry']

    def _junk_shadows(self):
        for reg in ('alt_af', 'alt_bc', 'alt_de', 'alt_hl'):
            setattr(self.cpu, reg, JUNK)

    # ---------- running ----------
    def run(self):
        """Run the program, as Asm( does."""
        self.build_vat()
        self._execute(USERMEM, {})

    def call(self, label, **regs):
        """Run one subroutine (a label from the .lab file) with the given registers (a=, hl=,
        de=, ...; the others are junk) until it returns; the CPU is left as it returned, so
        self.cpu.hl etc. are its results. The same checks apply as for run()."""
        self.build_vat()
        self._execute(self.labels[label.upper()], regs)
        return self.cpu

    def _execute(self, start, regs):
        cpu = self.cpu
        for reg in ('af', 'bc', 'de', 'hl', 'ix'):
            setattr(cpu, reg, JUNK)          # nothing may depend on a register's start value
        self._junk_shadows()
        for reg, value in regs.items():
            setattr(cpu, reg, value)
        cpu.iy = FLAGS
        cpu.iff1 = cpu.iff2 = 1
        self.mem[RET_SLOT:RET_SLOT + 2] = EXIT.to_bytes(2, 'little')
        cpu.sp = RET_SLOT
        cpu.pc = start
        cpu.ticks_to_stop = self.max_ticks
        while True:
            events = cpu.run()
            if events & cpu._TICKS_LIMIT_HIT:
                raise Z80Error('still running after %d T-states (PC %04Xh)' % (self.max_ticks, cpu.pc))
            if not events & cpu._BREAKPOINT_HIT:
                self._junk_shadows()         # end of the emulator's frame: as an interrupt would
                continue
            if cpu.pc == BCALL:
                # rst 28h pushed the address of the routine's word: run it, return past the word
                ret = int.from_bytes(self.mem[cpu.sp:cpu.sp + 2], 'little')
                self._bcall(int.from_bytes(self.mem[ret:ret + 2], 'little'))
                cpu.sp += 2
                cpu.pc = ret + 2
            elif cpu.pc == EXIT:
                break
            else:
                raise Z80Error('ran into ROM at %04Xh (a jump outside the program, or rst 38h)'
                               % cpu.pc)
        self.ticks = self.max_ticks - cpu.ticks_to_stop
        if cpu.sp != RET_SLOT + 2:
            raise Z80Error('returned with the stack at %04Xh, not %04Xh' % (cpu.sp, RET_SLOT + 2))
        if cpu.iy != FLAGS:
            raise Z80Error('IY changed to %04Xh' % cpu.iy)
        if not cpu.iff1:
            raise Z80Error('returned with interrupts disabled')
        if self.bank_a != OS_PAGE:
            raise Z80Error('returned with page %02Xh in bank A (port 6), not the OS\'s %02Xh'
                           % (self.bank_a, OS_PAGE))
