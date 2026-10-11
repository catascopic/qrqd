"""Engine tests for the standalone (QR-only) release: Notefolio notes (E=3 check or encode,
E=4 list). Name of the note in Str2, list of names in Str3.

  python tests/test_standalone_notefolio.py
"""
import random
import struct
import sys
from pathlib import Path

from qrtest import (ROOT, CAP_ALNUM, CAP_BYTE, Machine, SRC, check_symbol, decode, matrix_from,
                    AUTO, ASCII, ALNUM, BAD)

SRC = (ROOT / "src" / "standalone" / "QRSRC.axe.txt").read_text(encoding="utf-8")
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
# hyphen and negative sign -> -; every other byte goes through unchanged
SWAP = {0xC1: 91, 0x5B: 0xC1, 0xF2: 36, 0x24: 0xF2, 0xD6: 10, 0x0A: 0xD6,
        0xF1: 32, 0xD2: 45, 0x1A: 45}


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


def machine(notes, params, str2=None, extra=()):
    m = Machine(SRC)
    m.add_vat_other(0x05, 'QR')                             # a program
    m.add_appvar('SAVE', bytes(range(40)))                  # ordinary appvar
    m.add_vat_other(0x01, '\x5dBIN')                        # a named list
    for name, content, arch in notes:
        m.add_appvar(name, content, archived=arch)
    m.add_appvar('TINY', SIG + bytes(5))                    # too small to be a note
    m.add_appvar('FAKE', b'\x00\x47\xbf\xaf' + bytes(40))   # wrong signature
    m.add_appvar('lower', notefolio('lower', b'hi'))        # name can't be opened by name
    m.build_vat()
    for k, v in {'O': 0, 'A': 0, 'B': 0, **params}.items():
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

    # checking (V=0): 2*length + 1 if alphanumeric; a note never fails in byte mode,
    # B = position of the first non-ASCII character (left alone if none)
    for name, tb, _ in texts:
        alnum = all(chr(c) in ALNUM_SET for c in expected_bytes(tb))
        want = (2 * len(tb) + alnum, first_non_ascii(tb))
        m = machine(notes, {'E': NOTE, 'V': 0, 'M': AUTO}, str2=name)
        got = (m.ans, m.get_real('B'))
        expect('check %s = %d, B=%d' % ((name,) + want), got == want, got)
    m = machine(notes, {'E': NOTE, 'V': 0, 'M': ALNUM}, str2='NOTES')
    expect('check NOTES forced alnum: lowercase at 2', m.ans == BAD + 2, m.ans)
    up = [('UP', notefolio('UP', ti_text('AB θ')), False)]
    m = machine(up, {'E': NOTE, 'V': 0, 'M': ALNUM}, str2='UP')
    expect('check θ forced alnum fails at 4, B untouched', (m.ans, m.get_real('B')) == (BAD + 4, 0),
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
    # 2*16383+1 is the most Ans can carry; longer is "too long", even with a bad char past it
    for n, extra, want in ((16383, b'', 2 * 16383 + 1), (16384, b'', 65532), (16384, b'\x96', 65532)):
        big = [('BIG', notefolio('BIG', b'A' * n + extra), True)]
        m = machine(big, {'E': NOTE, 'V': 0, 'M': AUTO}, str2='BIG')
        expect('check a %d-character note -> %d' % (n + len(extra), want), m.ans == want, m.ans)
    for bad in ('SAVE', 'NOPE', 'TINY', 'FAKE'):
        m = machine(notes, {'E': NOTE, 'V': 0, 'M': AUTO}, str2=bad)
        expect('check %s -> 65535' % bad, m.ans == 65535, m.ans)

    count = 0
    for name, tb, _ in texts:
        payload = expected_bytes(tb)
        alnum = all(chr(c) in ALNUM_SET for c in payload)
        for v in range(1, 12):
            cap = (CAP_ALNUM if alnum else CAP_BYTE)[v - 1]
            for N in sorted({min(len(tb), cap), min(len(tb), cap) // 2}):
                m = machine(notes, {'E': NOTE, 'V': v, 'N': N, 'M': AUTO, 'A': int(alnum)}, str2=name)
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
    m = machine(allnote, {'E': NOTE, 'V': 11, 'N': 255, 'M': AUTO, 'A': 0}, str2='ALL')
    got = decode(matrix_from(m, 11))[0].bytes if m.ans == 0 else m.ans
    expect('every byte 1-255 encodes as mapped', got == expected_bytes(every), got)
    # one-to-one except the deliberate merges: wrap space with space, hyphen and negative with -
    expect('only wrap space, hyphen and negative share a byte with another character',
           len(set(expected_bytes(every))) == 255 - 3)


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


if __name__ == '__main__':
    real_file()
    synthetic()
    print('\n%s' % ('ALL PASSED' if not failures else '%d FAILED' % len(failures)))
    sys.exit(1 if failures else 0)
