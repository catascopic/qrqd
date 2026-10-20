"""Runs a compiled TI-83+ assembly program (.8xp) in a Z80 emulator, for the tests.

AsmMachine has the interface of axesim's Machine (set_real, get_real, set_str, set_list, run,
ans, displays, os, mem, full), so the engine tests can run the Z80 port of prgmθQR
(docs/asm_port.md) with `--asm` instead of the Axe source. The CPU is the `z80` package
(Ivan Kosarev's emulator, C++ core). What the calculator's OS does is modelled here:

- Memory: the TI-83+ RAM map. The program's code is copied to userMem (9D95h), as Asm( does.
  Writes are allowed only to the scratch areas (saveSScreen = L₁, plotSScreen = the graph
  buffer, appBackUpScreen = L₃), OP1-OP6, the program itself, the stack below the return
  address, and the data of OS variables the test created. Anything else (ROM, the OS's RAM,
  the caller's stack) raises.
- OS calls: bcall (rst 28h) runs a Python version of the routine; only those in BCALLS exist,
  any other raises. ROM is filled with FFh (rst 38h), so a jump into ROM stops at 0038h and
  raises instead of running.
- Ports: port 2 reads the model (bit 7 set on a TI-84+ or Silver Edition); port 20h (CPU
  speed) can be written on those only. Any other port raises.
- The final ret must come back to the pushed return address with the stack where it started,
  IY (the OS flags pointer) unchanged and interrupts still enabled.

No interrupts are generated (the emulator raises none by itself), so the OS's interrupt
handler, which would run during the program on a calculator, isn't modelled.
"""
from pathlib import Path

import z80

from axesim import Machine as AxeMachine     # for the 9-byte float conversions

USERMEM = 0x9D95
OP1 = 0x8478                 # OP1-OP6: 6 registers of 11 bytes
FLAGS = 0x89F0               # IY points here while the OS runs
L1, L3, L6 = 0x86EC, 0x9872, 0x9340   # saveSScreen, appBackUpScreen, plotSScreen (768 bytes each)
STACK_LOW = 0xFE70           # the OS stack: 400 bytes below FFFFh
EXIT = 0x0040                # return address pushed for the program: reaching it ends the run
RET_SLOT = 0xFFDE            # where that return address sits (above it: the OS's own stack)
VAR_DATA = 0xC000            # where the harness puts OS variables' data
BCALL, RST38 = 0x0028, 0x0038

BCALLS = {0x41BF: '_OP1Set0', 0x4ABF: '_StoAns'}


class Z80Error(Exception):
    pass


class AsmMachine:
    tifloat = staticmethod(AxeMachine.tifloat)
    untifloat = staticmethod(AxeMachine.untifloat)

    def __init__(self, program, model='84+', max_ticks=1_500_000_000):
        """program: a .8xp path, or the program's bytes (BB 6D, then the code). model: '83+'
        (6 MHz only) or '84+' (has 15 MHz). max_ticks: T-states before the run is stopped as
        a hang (1.5e9 is 100 s at 15 MHz)."""
        if isinstance(program, (str, Path)):
            from tivars import TIEntry
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
        self.os = {}                # (kind, name) -> pointer to the data, as in axesim
        self.ticks = 0              # T-states the last run took
        self.cpu = z80.Z80Machine()
        self.mem = self.cpu.memory
        self.mem[0:0x8000] = b'\xff' * 0x8000
        self.cpu.set_memory_block(USERMEM, self.code)
        self.var_ptr = VAR_DATA
        # every address is write-protected, then the allowed areas are opened
        self.cpu.set_write_callback(self._bad_write)
        self.cpu.mark_addrs(0, 0x10000, self.cpu.WRITE_MARK)
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

    # ---------- ports ----------
    def _port_in(self, port):
        port &= 0xFF
        if port == 2:
            return 0x80 if self.model == '84+' else 0x00
        raise Z80Error('in from port %02Xh (PC %04Xh)' % (port, self.cpu.pc))

    def _port_out(self, port, value):
        port &= 0xFF
        if port == 0x20 and self.model == '84+':
            self.full = bool(value & 1)
            return
        raise Z80Error('out %02Xh to port %02Xh on a %s (PC %04Xh)' % (value, port, self.model, self.cpu.pc))

    # ---------- OS variables (the engine can't find them yet: _ChkFindSym is milestone 2) ----------
    def _alloc(self, data):
        p = self.var_ptr
        self.mem[p:p + len(data)] = data
        self.writable(p, len(data))
        self.var_ptr += len(data) + 16
        return p

    def set_real(self, name, v):
        self.os[('real', name)] = self._alloc(self.tifloat(v))

    def get_real(self, name):
        p = self.os[('real', name)]
        return self.untifloat(bytes(self.mem[p:p + 9]))

    def set_str(self, n, toks):
        data = bytes(toks)
        self.os[('str', n)] = self._alloc(len(data).to_bytes(2, 'little') + data) + 2

    def set_list(self, name, values):
        data = len(values).to_bytes(2, 'little') + b''.join(self.tifloat(v) for v in values)
        self.os[('list', name)] = self._alloc(data) + 2

    def rd(self, p):
        return self.mem[p]

    # ---------- OS routines ----------
    def _bcall(self, addr):
        name = BCALLS.get(addr)
        if name is None:
            raise Z80Error('unknown bcall %04Xh' % addr)
        self.calls.append(name)
        if name == '_OP1Set0':
            self.mem[OP1:OP1 + 9] = self.tifloat(0)
        elif name == '_StoAns':
            self.ans = self.untifloat(bytes(self.mem[OP1:OP1 + 9]))

    # ---------- running ----------
    def run(self):
        cpu = self.cpu
        for reg in ('af', 'bc', 'de', 'hl', 'ix', 'alt_af', 'alt_bc', 'alt_de', 'alt_hl'):
            setattr(cpu, reg, 0x5A5A)        # nothing may depend on a register's start value
        cpu.iy = FLAGS
        cpu.iff1 = cpu.iff2 = 1
        self.mem[RET_SLOT:RET_SLOT + 2] = EXIT.to_bytes(2, 'little')
        cpu.sp = RET_SLOT
        cpu.pc = USERMEM
        cpu.ticks_to_stop = self.max_ticks
        while True:
            events = cpu.run()
            if events & cpu._TICKS_LIMIT_HIT:
                raise Z80Error('still running after %d T-states (PC %04Xh)' % (self.max_ticks, cpu.pc))
            if not events & cpu._BREAKPOINT_HIT:
                continue                     # end of the emulator's frame: carry on
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
