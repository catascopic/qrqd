"""Engine tests for Notefolio notes (E=3 check or encode, E=4 list). Name of the note in Str2,
list of names in Str3.

  python tests/test_notefolio.py
  --asm runs them against the Z80 port (build/_theta_QR.8xp, docs/asm_port.md)
"""
import random
import struct
import sys
from pathlib import Path

from qrtest import (ROOT, ASM, CAP_ALNUM, CAP_BYTE, Machine, SRC, check_symbol, decode,
                    matrix_from, AUTO, ASCII, ALNUM, BAD)

if not ASM:     # with --asm, qrtest's SRC is the Z80 port's .8xp
    SRC = (ROOT / "src" / "QRSRC.axe.txt").read_text(encoding="utf-8")
failures = []
SIG = bytes([0xF3, 0x47, 0xBF, 0xAF])
TI_FROM = {'\n': 0xD6, '[': 0xC1, '$': 0xF2, 'θ': 0x5B, 'é': 0x96, 'ñ': 0xB5, '⁴': 0x24}
ALNUM_SET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:'
NOTE = 3


def expect(name, cond, detail=''):
    print(('ok    ' if cond else 'FAIL  ') + name + ('' if cond else '  ' + str(detail)))
    if not cond:
        failures.append(name)


def ti_text(s, wrap_every=0):
    """Text -> calculator character codes, as Notefolio stores them (F1h = wrapped space)."""
    out = bytearray()
    for k, ch in enumerate(s):
        if ch in TI_FROM:
            out.append(TI_FROM[ch])
        elif ch == ' ' and wrap_every and k % wrap_every == 0:
            out.append(0xF1)
        else:
            out.append(ord(ch))
    return bytes(out)


# calculator [ $ Enter swap with θ ⁴ and the calculator's 0Ah; wrap space -> space;
# hyphen -> -; every other byte goes through unchanged (the negative sign 1Ah too: not ASCII)
SWAP = {0xC1: 91, 0x5B: 0xC1, 0xF2: 36, 0x24: 0xF2, 0xD6: 10, 0x0A: 0xD6,
        0xF1: 32, 0xD2: 45}


def expected_bytes(tb):
    """The bytes the engine encodes for a note."""
    return bytes(SWAP.get(c, c) for c in tb)


def first_non_ascii(tb):
    return next((k + 1 for k, c in enumerate(expected_bytes(tb)) if not (32 <= c <= 126 or c == 10)), 0)


def notefolio(title, tb):
    """Appvar contents in the layout NoteFolioEdit writes (and TEST.8xv confirms)."""
    size = len(tb) + 24
    return (SIG + bytes(4) + title.encode().ljust(8, b'\0')[:8] +
            size.to_bytes(2, 'little') + (24).to_bytes(2, 'little') +
            size.to_bytes(2, 'little') + (1).to_bytes(2, 'little') + tb + b'\0' + b'\0\0')


def machine(notes, params, str2=None, extra=(), arch_at=None):
    m = Machine(SRC)
    if arch_at is not None and not ASM:  # where archived data starts (axesim's default 4000h
        m.arch_ptr = arch_at             # holds 16 KB; the Z80 harness has real flash pages)
    m.add_vat_other(0x05, 'QR')                             # a program
    m.add_appvar('SAVE', bytes(range(40)))                  # ordinary appvar
    m.add_vat_other(0x01, '\x5dBIN')                        # a named list
    for name, content, arch in notes:
        m.add_appvar(name, content, archived=arch)
    m.add_appvar('TINY', SIG + bytes(5))                    # too small to be a note
    m.add_appvar('FAKE', b'\x00\x47\xbf\xaf' + bytes(40))   # wrong signature
    m.add_appvar('lower', notefolio('lower', b'hi'))        # name can't be opened by name
    m.build_vat()
    for k, v in {'O': 0, 'B': 0, **params}.items():
        m.set_real(k, v)
    if str2 is not None:
        m.set_str(2, str2.encode().ljust(8, b'\x29'))        # padded with space tokens
    m.run()
    return m


def synthetic():
    random.seed(7)
    texts = [('NOTES', ti_text('Hello [world] costs $5\nLine two'), False),
             ('TODO2', ti_text('buy milk and eggs and bread and more', 6), True),
             ('LONG', ti_text(''.join(random.choice('abcdefghij KLMNOP\n-.,') for _ in range(700))), True),
             ('SHOUT', ti_text('HELLO WORLD $5 50% OFF: A-B/C.D*E+F'), False),
             ('ODD', ti_text('Line two θ ⁴ é ñ'), False),
             ('E', b'', False)]
    notes = [(n, notefolio(n, tb), arch) for n, tb, arch in texts]

    m = machine(notes, {'E': 4})
    s3 = m.os[("str", 3)]
    s3b = bytes(m.mem[s3:s3 + m.rd16(s3 - 2)])
    want = b''.join(n.encode().ljust(8, b'\x29') for n, _, _ in texts) + b'\x29' * 48
    expect('list mode finds only the %d real notes (RAM + archived)' % len(texts),
           m.ans == len(texts) and s3b == want, (m.ans, s3b[:40]))

    # checking (V=0): 2*length + 1 if alphanumeric (M left alone); a note never fails in byte mode,
    # B = position of the first non-ASCII character (left alone if none)
    for name, tb, _ in texts:
        alnum = all(chr(c) in ALNUM_SET for c in expected_bytes(tb))
        want = (2 * len(tb) + alnum, first_non_ascii(tb), AUTO)
        m = machine(notes, {'E': NOTE, 'V': 0, 'M': AUTO}, str2=name)
        got = (m.ans, m.get_real('B'), m.get_real('M'))
        expect('check %s = %d, B=%d, M=%d' % ((name,) + want), got == want, got)
    m = machine(notes, {'E': NOTE, 'V': 0, 'M': ALNUM}, str2='NOTES')
    expect('check NOTES forced alnum: lowercase at 2', (m.ans, m.get_real('B')) == (BAD, 2), m.ans)
    up = [('UP', notefolio('UP', ti_text('AB θ')), False)]
    m = machine(up, {'E': NOTE, 'V': 0, 'M': ALNUM}, str2='UP')
    expect('check θ forced alnum fails at 4 (in B)', (m.ans, m.get_real('B')) == (BAD, 4),
           (m.ans, m.get_real('B')))
    m = machine(notes, {'E': NOTE, 'V': 0, 'M': ASCII}, str2='SHOUT')
    expect('check SHOUT forced ASCII', m.ans == 2 * len(texts[3][1]), m.ans)
    m = machine(notes, {'E': NOTE, 'V': 0, 'M': ASCII}, str2='ODD')
    expect('check ODD forced ASCII warns at 10', (m.ans, m.get_real('B')) == (2 * len(texts[4][1]), 10),
           (m.ans, m.get_real('B')))
    every = bytes(range(1, 256))
    allnote = [('ALL', notefolio('ALL', every), False)]
    m = machine(allnote, {'E': NOTE, 'V': 0, 'M': AUTO}, str2='ALL')
    expect('check every byte 1-255: length 255, first non-ASCII at 1',
           (m.ans, m.get_real('B')) == (2 * 255, 1), (m.ans, m.get_real('B')))
    # 2*32765+1 stays below the error codes; longer is "too long", even with a bad char past it
    for n, extra, want in ((32765, b'', 2 * 32765 + 1), (32766, b'', 65532), (32766, b'\x96', 65532)):
        big = [('BIG', notefolio('BIG', b'A' * n + extra), True)]
        # a 32 KB archived note: start the archive at 0 so it ends just past 8000h, in RAM
        # nothing uses, instead of running into L1 (a real one is in flash pages)
        m = machine(big, {'E': NOTE, 'V': 0, 'M': AUTO}, str2='BIG', arch_at=0)
        expect('check a %d-character note -> %d' % (n + len(extra), want), m.ans == want, m.ans)
    # no 00h after the text: the appvar's size ends it (size 24 + 5)
    for arch in (False, True):
        noz = [('NOZ', notefolio('NOZ', b'ABCDE')[:-3], arch)]
        m = machine(noz, {'E': NOTE, 'V': 0, 'M': AUTO}, str2='NOZ')
        expect('check a note with no 00h (%s): length 5 -> 11' % ('archived' if arch else 'RAM'),
               m.ans == 11, m.ans)
    for bad in ('SAVE', 'NOPE', 'TINY', 'FAKE'):
        m = machine(notes, {'E': NOTE, 'V': 0, 'M': AUTO}, str2=bad)
        expect('check %s -> 65535' % bad, m.ans == 65535, m.ans)

    # drawing in auto mode with no check first: the engine decides the mode itself
    count = 0
    for name, tb, _ in texts:
        payload = expected_bytes(tb)
        alnum = all(chr(c) in ALNUM_SET for c in payload)
        for v in range(1, 12):
            cap = (CAP_ALNUM if alnum else CAP_BYTE)[v - 1]
            for N in sorted({min(len(tb), cap), min(len(tb), cap) // 2}):
                m = machine(notes, {'E': NOTE, 'V': v, 'N': N, 'M': AUTO}, str2=name)
                try:
                    check_symbol(m, v, payload[:N], 'alphanumeric' if alnum else 'byte')
                except AssertionError as e:
                    expect('encode %s v%d N=%d' % (name, v, N), False, e)
                    return
                count += 1
    expect('%d note symbols match the reference and decode' % count, True)

    m = machine(notes, {'E': NOTE, 'V': 2, 'N': 4, 'M': AUTO, 'O': 4}, str2='TODO2')
    got = decode(matrix_from(m, 2))[0].bytes if m.ans == 0 else m.ans
    expect('skip 4 characters of a note', got == b'milk', got)

    # non-ASCII characters keep their calculator codes, with the swaps (θ -> C1h, ⁴ -> F2h)
    m = machine(notes, {'E': NOTE, 'V': 2, 'N': 16, 'M': AUTO}, str2='ODD')
    got = decode(matrix_from(m, 2))[0].bytes if m.ans == 0 else m.ans
    expect('ODD encodes θ ⁴ é ñ as C1 F2 96 B5', got == b'Line two \xc1 \xf2 \x96 \xb5', got)
    m = machine(allnote, {'E': NOTE, 'V': 11, 'N': 255, 'M': AUTO}, str2='ALL')
    got = decode(matrix_from(m, 11))[0].bytes if m.ans == 0 else m.ans
    expect('every byte 1-255 encodes as mapped', got == expected_bytes(every), got)
    # one-to-one except the deliberate merges: wrap space with space, hyphen with -
    expect('only wrap space and hyphen share a byte with another character',
           len(set(expected_bytes(every))) == 255 - 2)


def real_file():
    """TEST.8xv as saved by the user's calculator (archived; text with an F1h wrap marker)."""
    b = (ROOT / 'tests' / 'data' / 'TEST.8xv').read_bytes()
    data = b[55:55 + struct.unpack_from('<H', b, 53)[0]]
    name = data[5:13].rstrip(b'\0').decode()
    archived = bool(data[14] & 0x80)
    content = data[19:19 + struct.unpack_from('<H', data, 17)[0]]
    notes = [(name, content, archived)]
    m = machine(notes, {'E': NOTE, 'V': 0, 'M': AUTO}, str2=name)
    expect('TEST.8xv checks as 44 ASCII characters', m.ans == 2 * 44, m.ans)
    m = machine(notes, {'E': NOTE, 'V': 3, 'N': 44, 'M': AUTO}, str2=name)
    got = decode(matrix_from(m, 3))[0].bytes if m.ans == 0 else m.ans
    expect('TEST.8xv decodes to the pangram', got == b'The quick brown fox jumps over the lazy dog.', got)


def asm_list():
    """The Z80 port only: making Str3 with the OS (axesim's GetCalc just allocates)."""
    def str3(m):
        p = m.os[('str', 3)]
        return bytes(m.mem[p:p + m.rd16(p - 2)])

    def run(notes, setup=None):
        m = Machine(SRC)
        for name, content, arch in notes:
            m.add_appvar(name, content, archived=arch)
        if setup:
            setup(m)
        m.set_real('E', 4)
        m.run()
        return m
    one = [('ONE', notefolio('ONE', b'x'), False)]
    m = run(one, lambda m: m.set_str(3, b'old text that is longer than the list'))
    expect('asm: an old Str3 is replaced (deleted, then made again)',
           m.ans == 1 and str3(m) == b'ONE' + b'\x29' * 53 and m.calls.count('_DelVarArc') == 1,
           (m.ans, str3(m)[:12]))
    m = run(one, lambda m: m.set_str(3, b'old', archived=True))
    expect('asm: an archived Str3 is deleted too', m.ans == 1 and str3(m) == b'ONE' + b'\x29' * 53)
    m = run([])
    expect('asm: no notes: Ans 0, Str3 is the 48 spaces', m.ans == 0 and str3(m) == b'\x29' * 48)

    def low(m):
        m.set_str(3, b'keep')
        m.free_ram = 8 + 48 + 31          # one byte short of the string + 32
    m = run(one, low)
    expect('asm: not enough RAM: 65535, the old Str3 kept', m.ans == 65535 and str3(m) == b'keep'
           and '_CreateStrng' not in m.calls, (m.ans, str3(m)))
    m = run(one, lambda m: setattr(m, 'free_ram', 8 + 48 + 32))
    expect('asm: just enough RAM: listed', m.ans == 1, m.ans)
    many = [('N%d' % k, notefolio('N%d' % k, b'a'), k % 2 == 0) for k in range(85)]
    m = run(many)
    names = str3(m)
    expect('asm: at most 80 notes, the first 80 in VAT order', m.ans == 80 and len(names) == 80 * 8 + 48
           and names[:8] == b'N0' + b'\x29' * 6 and names[79 * 8:80 * 8] == b'N79' + b'\x29' * 5,
           (m.ans, len(names)))


if __name__ == '__main__':
    real_file()
    synthetic()
    if ASM:
        asm_list()
    print('\n%s' % ('ALL PASSED' if not failures else '%d FAILED' % len(failures)))
    sys.exit(1 if failures else 0)
