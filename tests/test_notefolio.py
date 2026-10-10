"""Engine tests for Notefolio notes (E=3 check or encode, E=4 list).

  python tests/test_notefolio.py
"""
import random
import struct
import sys
from pathlib import Path

from qrtest import (CAP_ALNUM, CAP_BYTE, Machine, SRC, check_symbol, decode, matrix_from,
                    AUTO, ASCII, ALNUM, BAD)

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


def expected_ascii(tb):
    """What the engine reads a note as; None for a character it can't encode."""
    out = []
    for c in tb:
        if c == 0xD6: out.append(10)               # Enter -> newline
        elif c == 0xF1: out.append(32)             # wrap marker -> space
        elif c == 0xC1: out.append(91)             # calculator [ -> [
        elif c == 0xF2: out.append(36)             # calculator $ -> $
        elif c in (0xD2, 0x1A): out.append(45)     # hyphen, negative sign -> -
        elif 32 <= c <= 126 and c not in (0x24, 0x5B): out.append(c)
        else: out.append(None)                     # θ, ⁴, accents, ...
    return out


def notefolio(title, tb):
    """Appvar contents in the layout NoteFolioEdit writes (and TEST.8xv confirms)."""
    size = len(tb) + 24
    return (SIG + bytes(4) + title.encode().ljust(8, b'\0')[:8] +
            size.to_bytes(2, 'little') + (24).to_bytes(2, 'little') +
            size.to_bytes(2, 'little') + (1).to_bytes(2, 'little') + tb + b'\0' + b'\0\0')


def machine(notes, params, str3=None, extra=()):
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
    for k, v in {'O': 0, **params}.items():
        m.set_real(k, v)
    if str3 is not None:
        m.set_str(3, str3.encode().ljust(8, b'\x29'))        # padded with space tokens
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
    s2 = m.os[('str', 2)]
    s2b = bytes(m.mem[s2:s2 + m.rd16(s2 - 2)])
    want = b''.join(n.encode().ljust(8, b'\x29') for n, _, _ in texts) + b'\x29' * 48
    expect('list mode finds only the %d real notes (RAM + archived)' % len(texts),
           m.ans == len(texts) and s2b == want, (m.ans, s2b[:40]))

    # checking (V=0): 2*length + 1 if alphanumeric, or BAD + position of the first bad char
    for name, tb, _ in texts:
        chars = expected_ascii(tb)
        alnum = all(c is not None and chr(c) in ALNUM_SET for c in chars)
        first_bad = next((k + 1 for k, c in enumerate(chars) if c is None), 0)
        want = BAD + first_bad if first_bad else 2 * len(tb) + alnum
        m = machine(notes, {'E': NOTE, 'V': 0, 'M': AUTO}, str3=name)
        expect('check %s = %d' % (name, want), m.ans == want, m.ans)
    m = machine(notes, {'E': NOTE, 'V': 0, 'M': ALNUM}, str3='NOTES')
    expect('check NOTES forced alnum: lowercase at 2', m.ans == BAD + 2, m.ans)
    m = machine(notes, {'E': NOTE, 'V': 0, 'M': ASCII}, str3='SHOUT')
    expect('check SHOUT forced ASCII', m.ans == 2 * len(texts[3][1]), m.ans)
    for bad in ('SAVE', 'NOPE', 'TINY', 'FAKE'):
        m = machine(notes, {'E': NOTE, 'V': 0, 'M': AUTO}, str3=bad)
        expect('check %s -> 65535' % bad, m.ans == 65535, m.ans)

    count = 0
    for name, tb, _ in texts:
        chars = expected_ascii(tb)
        if None in chars:
            continue
        payload = bytes(chars)
        alnum = all(chr(c) in ALNUM_SET for c in chars)
        for v in range(1, 12):
            cap = (CAP_ALNUM if alnum else CAP_BYTE)[v - 1]
            for N in sorted({min(len(tb), cap), min(len(tb), cap) // 2}):
                m = machine(notes, {'E': NOTE, 'V': v, 'N': N, 'M': AUTO}, str3=name)
                try:
                    check_symbol(m, v, payload[:N].decode(), 'alphanumeric' if alnum else 'byte')
                except AssertionError as e:
                    expect('encode %s v%d N=%d' % (name, v, N), False, e)
                    return
                count += 1
    expect('%d note symbols match the reference and decode' % count, True)

    m = machine(notes, {'E': NOTE, 'V': 2, 'N': 4, 'M': AUTO, 'O': 4}, str3='TODO2')
    got = decode(matrix_from(m, 2))[0].bytes if m.ans == 0 else m.ans
    expect('skip 4 characters of a note', got == b'milk', got)

    m = machine(notes, {'E': NOTE, 'V': 2, 'N': 16, 'M': AUTO}, str3='ODD')
    expect('encoding a note with a bad char fails at 10, nothing drawn',
           m.ans == BAD + 10 and not m.displays, m.ans)


def real_file():
    """TEST.8xv as saved by the user's calculator (archived; text with an F1h wrap marker)."""
    b = (Path(__file__).parent / 'data' / 'TEST.8xv').read_bytes()
    data = b[55:55 + struct.unpack_from('<H', b, 53)[0]]
    name = data[5:13].rstrip(b'\0').decode()
    archived = bool(data[14] & 0x80)
    content = data[19:19 + struct.unpack_from('<H', data, 17)[0]]
    notes = [(name, content, archived)]
    m = machine(notes, {'E': NOTE, 'V': 0, 'M': AUTO}, str3=name)
    expect('TEST.8xv checks as 44 ASCII characters', m.ans == 2 * 44, m.ans)
    m = machine(notes, {'E': NOTE, 'V': 3, 'N': 44, 'M': AUTO}, str3=name)
    got = decode(matrix_from(m, 3))[0].bytes if m.ans == 0 else m.ans
    expect('TEST.8xv decodes to the pangram', got == b'The quick brown fox jumps over the lazy dog.', got)


if __name__ == '__main__':
    real_file()
    synthetic()
    print('\n%s' % ('ALL PASSED' if not failures else '%d FAILED' % len(failures)))
    sys.exit(1 if failures else 0)
