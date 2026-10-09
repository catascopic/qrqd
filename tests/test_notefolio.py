"""Engine tests for the Notefolio modes (E=3 encode, E=4 list, E=5 measure).

  python tests/test_notefolio.py
"""
import random
import struct
import sys
from pathlib import Path

from qrtest import CAP_BYTE, Machine, SRC, check_symbol, decode, matrix_from

failures = []
SIG = bytes([0xF3, 0x47, 0xBF, 0xAF])
TI_FROM = {'\n': 0xD6, '[': 0xC1, 'θ': 0x5B, 'é': 0x96, 'ñ': 0xB5, '⁴': 0x24}


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
    out = bytearray()
    for c in tb:
        if c == 0xD6: out.append(10)               # Enter -> newline
        elif c == 0xF1: out.append(32)             # wrap marker -> space
        elif c == 0xC1: out.append(91)             # calculator [ -> [
        elif c in (0xD2, 0x1A): out.append(45)     # hyphen, negative sign -> -
        elif 32 <= c <= 126 and c not in (0x24, 0x5B): out.append(c)
        else: out.append(63)                       # anything else -> ?
    return bytes(out)


def notefolio(title, tb):
    """Appvar contents in the layout NoteFolioEdit writes (and TEST.8xv confirms)."""
    size = len(tb) + 24
    return (SIG + bytes(4) + title.encode().ljust(8, b'\0')[:8] +
            size.to_bytes(2, 'little') + (24).to_bytes(2, 'little') +
            size.to_bytes(2, 'little') + (1).to_bytes(2, 'little') + tb + b'\0' + b'\0\0')


def machine(notes, params, str5=None, extra=()):
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
    for k, v in params.items():
        m.set_real(k, v)
    if str5 is not None:
        m.set_str(5, str5.encode().ljust(8, b'\x29'))        # padded with space tokens
    m.run()
    return m


def synthetic():
    random.seed(7)
    texts = [('NOTES', ti_text('Hello [world]\nLine two θ ⁴ é ñ'), False),
             ('TODO2', ti_text('buy milk and eggs and bread and more', 6), True),
             ('LONG', ti_text(''.join(random.choice('abcdefghij KLMNOP\n-.,') for _ in range(700))), True),
             ('E', b'', False)]
    notes = [(n, notefolio(n, tb), arch) for n, tb, arch in texts]

    m = machine(notes, {'E': 4})
    s4 = m.os[('str', 4)]
    s4b = bytes(m.mem[s4:s4 + m.rd16(s4 - 2)])
    want = b''.join(n.encode().ljust(8, b'\x29') for n, _, _ in texts) + b'\x29' * 48
    expect('list mode finds only the 4 real notes (RAM + archived)', m.ans == 4 and s4b == want, (m.ans, s4b[:40]))

    for name, tb, _ in texts:
        m = machine(notes, {'E': 5}, str5=name)
        expect('measure %s = %d' % (name, len(tb)), m.ans == len(tb), m.ans)
    for bad in ('SAVE', 'NOPE', 'TINY', 'FAKE'):
        m = machine(notes, {'E': 5}, str5=bad)
        expect('measure %s -> 65535' % bad, m.ans == 65535, m.ans)

    count = 0
    for name, tb, _ in texts:
        for v in range(1, 12):
            cap = CAP_BYTE[v - 1]
            for N in sorted({min(len(tb), cap), min(len(tb), cap) // 2}):
                m = machine(notes, {'E': 3, 'V': v, 'N': N, 'C': 1, 'S': 0}, str5=name)
                try:
                    check_symbol(m, v, 1, expected_ascii(tb[:N]), 'byte')
                except AssertionError as e:
                    expect('encode %s v%d N=%d' % (name, v, N), False, e)
                    return
                count += 1
    expect('%d note symbols match the reference and decode' % count, True)

    tb = texts[0][1]
    first_bad = next(i for i, c in enumerate(expected_ascii(tb)) if c == 63) + 1
    m = machine(notes, {'E': 3, 'V': 2, 'N': len(tb), 'C': 1, 'S': 1}, str5='NOTES')
    expect('safe mode reports first non-ASCII char at %d' % first_bad, m.ans == first_bad and not m.displays, m.ans)


def real_file():
    """TEST.8xv as saved by the user's calculator (archived; text with an F1h wrap marker)."""
    b = (Path(__file__).parent / 'data' / 'TEST.8xv').read_bytes()
    data = b[55:55 + struct.unpack_from('<H', b, 53)[0]]
    name = data[5:13].rstrip(b'\0').decode()
    archived = bool(data[14] & 0x80)
    content = data[19:19 + struct.unpack_from('<H', data, 17)[0]]
    notes = [(name, content, archived)]
    m = machine(notes, {'E': 5}, str5=name)
    expect('TEST.8xv measures 44', m.ans == 44, m.ans)
    m = machine(notes, {'E': 3, 'V': 3, 'N': 44, 'C': 1, 'S': 1}, str5=name)
    got = decode(matrix_from(m, 3, 1))[0].bytes if m.ans == 0 else m.ans
    expect('TEST.8xv decodes to the pangram', got == b'The quick brown fox jumps over the lazy dog.', got)


if __name__ == '__main__':
    real_file()
    synthetic()
    print('\n%s' % ('ALL PASSED' if not failures else '%d FAILED' % len(failures)))
    sys.exit(1 if failures else 0)
