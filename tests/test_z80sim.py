"""Tests for the Z80 harness itself (tools/z80sim.py): tiny hand-assembled programs that do
one thing each, right or wrong. Each mistake must raise, so a bug in the assembly engine
can't pass the engine tests by doing something a calculator wouldn't survive.

  python tests/test_z80sim.py
"""
import sys

from qrtest import ROOT                          # noqa: F401 (puts tools/ on the path)
from z80sim import AsmMachine, Z80Error, ARCH_PAGE, SYMTABLE, PROGPTR, PTEMP

HEAD = b'\xbb\x6d'
STO_ANS_0 = bytes.fromhex('efbf41' 'efbf4a')    # bcall(_OP1Set0) : bcall(_StoAns)
RET = b'\xc9'

failures = []


def expect(name, cond, detail=''):
    print(('ok    ' if cond else 'FAIL  ') + name + ('' if cond else '  ' + str(detail)))
    if not cond:
        failures.append(name)


def run(code, **kw):
    m = AsmMachine(HEAD + bytes.fromhex(code) if isinstance(code, str) else HEAD + code, **kw)
    m.run()
    return m


def find(setup, name):
    """Run _ChkFindSym on an OP1 name (9 bytes) in a machine prepared by setup(m): the program
    copies the name to OP1, calls it, and stores DE, carry (FFh if set) and B in L1."""
    code = bytes.fromhex('21b09d' '117884' '010900' 'edb0' 'eff142'   # ld hl,name: ld de,OP1:
                         'ed53ec86' '9f' '32ee86' '78' '32ef86' 'c9')  # ld bc,9: ldir: bcall
    assert 0x9D95 + len(code) == 0x9DB0                                # the name follows
    m = AsmMachine(HEAD + code + name.ljust(9, b'\0'))
    setup(m)
    m.run()
    return m.mem[0x86EE] == 0xFF, m.mem[0x86EC] | m.mem[0x86ED] << 8, m.mem[0x86EF], m


def fails(name, code, words, **kw):
    """The program must raise a Z80Error whose message contains `words`."""
    try:
        run(code, **kw)
        expect(name, False, 'no error')
    except Z80Error as e:
        expect(name, words in str(e), e)


if __name__ == '__main__':
    m = run(STO_ANS_0 + RET)
    expect('Ans = 0 through _OP1Set0 and _StoAns', m.ans == 0 and m.calls == ['_OP1Set0', '_StoAns'])
    m = run('3e01' '32ec86' '324093' '327298' 'c5c1' + STO_ANS_0.hex() + 'c9')
    expect('writes to L1, the graph buffer, L3 and the stack are allowed', m.ans == 0)
    m = run('db02' 'c9', model='83+')
    expect('port 2 can be read on a TI-83+', m.ans is None)
    m = run('3e01d320' 'c9')
    expect('15 MHz on a TI-84+ sets full', m.full)

    fails('a write to ROM raises', '320010' 'c9', 'write')
    fails("a write to the OS's RAM raises", '320080' 'c9', 'write')
    fails("overwriting the caller's return address raises", '210000' '22deff' 'c9', 'write')
    fails('an unknown bcall raises', 'ef0040' 'c9', 'unknown bcall')
    fails('returning with the stack off raises', '214000' 'e5' 'c9', 'stack')
    fails('changing IY raises', 'fd23' 'c9', 'IY')
    fails('returning with interrupts off raises', 'f3' 'c9', 'interrupts')
    fails('a jump into ROM raises', 'c30020', 'outside the program')
    fails('a ret with a value left on the stack (to 5A5Ah) raises', 'c5' 'c9', 'outside the program')
    fails('a hang is stopped', '18fe', 'still running', max_ticks=100_000)
    fails('an unknown port raises', 'db01' 'c9', 'port 01h')
    fails('the speed port on a TI-83+ raises', '3e01d320' 'c9', 'port 20h', model='83+')
    m = run('21d204' 'ef9247' 'ef5641' 'efbf4a' 'c9')     # HL=1234, _SetXXXXOP2, _OP2ToOP1, _StoAns
    expect('Ans = HL through _SetXXXXOP2, _OP2ToOP1, _StoAns', m.ans == 1234, m.ans)
    m = run('013412' 'efbf41' 'ed43ec86' 'c9')            # BC survives a bcall?
    expect('a bcall leaves junk in registers it does not return', m.mem[0x86EC:0x86EE] == b'\x5a\x5a')
    m = run('d9013412d9' 'efbf41' 'd9ed43ec86d9' 'c9')    # the same in the shadow BC
    expect('a bcall leaves junk in the shadow registers', m.mem[0x86EC:0x86EE] == b'\x5a\x5a')

    def vars_(m):
        m.set_real('E', 7)
        m.set_real('V', 3)
        m.set_str(1, b'AB')
        m.set_list('E', [1, 2])          # a list named E: in the program table, not the real
        m.set_list('BIN', [5])
        m.set_str(2, b'X', archived=True)
    real_e, str1, list_bin = b'\x00E', b'\x04\xaa\x00', b'\x01\x5dBIN'
    carry, de, b, m = find(vars_, real_e)
    expect('_ChkFindSym finds real E (not list E): DE = its float, B = 0',
           not carry and de == m.os[('real', 'E')] and b == 0 and m.get_real('E') == 7, (carry, de, b))
    carry, de, b, m = find(vars_, str1)
    expect('_ChkFindSym finds Str1: DE = its size word', not carry and de == m.os[('str', 1)] - 2
           and m.mem[de] == 2, (carry, de))
    carry, de, b, m = find(vars_, list_bin)
    expect('_ChkFindSym finds list BIN: DE = its size word', not carry and de == m.os[('list', 'BIN')] - 2
           and m.mem[de] == 1, (carry, de))
    carry, de, b, m = find(vars_, b'\x01\x5dE')
    expect('_ChkFindSym finds list E (not real E)', not carry and de == m.os[('list', 'E')] - 2)
    carry, de, b, m = find(vars_, b'\x04\xaa\x01')
    expect('_ChkFindSym finds archived Str2: B = its flash page, DE in 4000h-7FFFh',
           not carry and b == ARCH_PAGE and 0x4000 <= de < 0x8000, (carry, de, b))
    for label, name in (('real M', b'\x00M'), ('Str3', b'\x04\xaa\x02'), ('list BI', b'\x01\x5dBI'),
                        ('list BINX', b'\x01\x5dBINX')):
        expect('_ChkFindSym: no %s -> carry' % label, find(vars_, name)[0])
    expect('_ChkFindSym in an empty VAT -> carry', find(lambda m: None, real_e)[0])
    # the VAT's layout: real E's entry at symTable, names downwards; lists in the program table
    m = AsmMachine(HEAD + RET)
    vars_(m)
    m.build_vat()
    e = m.mem[SYMTABLE - 8:SYMTABLE + 1]
    prog = int.from_bytes(m.mem[PROGPTR:PROGPTR + 2], 'little')
    ptemp = int.from_bytes(m.mem[PTEMP:PTEMP + 2], 'little')
    p = m.os[('real', 'E')]
    expect('VAT: real E first in the symbol table (type, T2, version, pointer, page, name)',
           bytes(e) == bytes([0, 0, ord('E'), 0, p >> 8, p & 0xFF, 0, 0, 0]), bytes(e).hex(' '))
    expect('VAT: 4 symbol-table entries (E, V, Str1, Str2), then lists E and BIN', prog == SYMTABLE - 36
           and ptemp == prog - (7 + 2) - (7 + 4) and m.mem[prog] == 1 and m.mem[prog - 6] == 2,
           (hex(prog), hex(ptemp)))
    # the archive: an entry as the OS writes it, from 16 bytes before the end of page 0Bh
    m = AsmMachine(HEAD + RET)
    m.add_appvar('NOTE', b'hello world', archived=True)
    m.build_vat()
    entry = bytes(m.flash[0x0B][0x3FF0:]) + bytes(m.flash[0x0C][:11])
    rest = bytes([0x15, 0, 0, 0xF0, 0x7F, 0x0B, 4]) + b'NOTE' + (11).to_bytes(2, 'little') + b'hello world'
    expect('archive entry: FCh, size of the rest, VAT copy, name, size word, data, across pages',
           entry == b'\xfc' + len(rest).to_bytes(2, 'little') + rest, entry.hex(' '))
    carry, de, b, m = find(lambda m: m.add_appvar('NOTE', b'hi', archived=True), b'\x15NOTE')
    expect('_ChkFindSym: archived appvar -> B = page 0Bh, DE = its FCh byte (7FF0h)',
           not carry and (b, de) == (0x0B, 0x7FF0), (carry, hex(de), b))
    code = '060c' '210640' 'ef1d50' '79' '32ec86' 'c9'    # ld b,0Ch: ld hl,4006h: bcall: ld (L1),c
    m = AsmMachine(HEAD + bytes.fromhex(code))
    m.add_appvar('NOTE', b'hello world', archived=True)
    m.run()
    expect('_LoadCIndPaged: C = the byte at page B, address HL', m.mem[0x86EC] == ord('w'), m.mem[0x86EC])
    def arch(m):
        m.add_appvar('NOTE', b'x', archived=True)
    fails('a read of 4000h-7FFFh with the OS page in bank A raises', '3a0040' 'c9', 'read from 4000h')
    # port 6: map page 0Ch, read 4006h, put the old page back (in a,(6): ld e,a: ld a,0Ch:
    # out (6),a: ld a,(4006h): ld (L1),a: ld a,e: out (6),a: ret)
    m = AsmMachine(HEAD + bytes.fromhex('db06' '5f' '3e0c' 'd306' '3a0640' '32ec86' '7b' 'd306' 'c9'))
    m.add_appvar('NOTE', b'hello world', archived=True)
    m.run()
    expect('port 6: an archive page mapped into bank A reads at 4000h-7FFFh', m.mem[0x86EC] == ord('w'),
           m.mem[0x86EC])
    fails('returning with an archive page in bank A raises', '3e0c' 'd306' 'c9', 'bank A')
    fails('a read with a page that holds no archive in bank A raises', '3e20' 'd306' '3a0040' 'c9', 'holds no')
    m = AsmMachine(HEAD + bytes.fromhex('060c' '210080' 'ef1d50' 'c9'))
    arch(m)
    try:
        m.run()
        expect('_LoadCIndPaged outside 4000h-7FFFh raises', False)
    except Z80Error as e:
        expect('_LoadCIndPaged outside 4000h-7FFFh raises', 'outside' in str(e), e)
    m = AsmMachine(HEAD + bytes.fromhex('0620' '210040' 'ef1d50' 'c9'))
    arch(m)
    try:
        m.run()
        expect('_LoadCIndPaged from a page with no archive raises', False)
    except Z80Error as e:
        expect('_LoadCIndPaged from a page with no archive raises', 'holds no' in str(e), e)
    # _CreateStrng: Str3 of 5 bytes (ld hl,name: ld de,OP1: ld bc,9: ldir: ld hl,5: bcall: ret)
    make = bytes.fromhex('21a79d' '117884' '010900' 'edb0' '210500' 'ef2743' 'c9')
    assert 0x9D95 + len(make) == 0x9DA7                                # the name follows
    make += bytes([0x04, 0xAA, 0x02]) + bytes(6)
    m = AsmMachine(HEAD + make)
    m.run()
    p = m.os.get(('str', 3))
    expect('_CreateStrng makes Str3 (size word 5) in the VAT', p and m.rd16(p - 2) == 5
           and any(name == b'\xaa\x02' for _, typ, name, _, _ in m.vat_entries() if typ == 4))
    m = AsmMachine(HEAD + make)
    m.set_str(3, b'x')
    try:
        m.run()
        expect('_CreateStrng on an existing Str3 raises', False)
    except Z80Error as e:
        expect('_CreateStrng on an existing Str3 raises', 'exists' in str(e), e)
    m = AsmMachine(HEAD + make)
    m.free_ram = 15
    try:
        m.run()
        expect('_CreateStrng without the RAM raises ERR:MEMORY', False)
    except Z80Error as e:
        expect('_CreateStrng without the RAM raises ERR:MEMORY', 'MEMORY' in str(e), e)
    try:
        AsmMachine(b'\x3a' + RET)
        expect('a program without BB 6D is refused', False)
    except Z80Error:
        expect('a program without BB 6D is refused', True)

    print('\n%s' % ('ALL PASSED' if not failures else '%d FAILED' % len(failures)))
    sys.exit(1 if failures else 0)
