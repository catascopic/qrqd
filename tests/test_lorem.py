"""Tests for LOREMSRC (src/LOREMSRC.axe.txt), the tool that writes a long Notefolio note.

LOREM is run in axesim with N set (or missing); the appvar it creates must have the layout
of a real note, and the QR engine must read it like any other note.

  python tests/test_lorem.py
"""
import sys

from qrtest import ROOT, Machine, decode, matrix_from, AUTO
from test_notefolio import machine, expect, failures, SIG

SRC = (ROOT / 'src' / 'LOREMSRC.axe.txt').read_text(encoding='utf-8')
TEXT = ('Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt '
        'ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation '
        'ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in '
        'reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur '
        'sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id '
        'est laborum.').encode()


class Recording(Machine):
    def appvar_create(self, name, size):
        self.requested = size
        return super().appvar_create(name, size)


def lorem(n=None, free=12000):
    m = Recording(SRC)
    m.free_ram = free
    if n is not None:
        m.set_real('N', n)
    m.run()
    p = m.appvars.get('LOREM', (None,))[0]
    return m, (bytes(m.mem[p:p + m.rd16(p - 2)]) if p else None)


def note(copies):
    """What LOREM should write for this many copies: a note like NoteFolioEdit's."""
    text = b'\xd6'.join([TEXT] * copies)
    size = len(text) + 24
    return (SIG + bytes([0x80, 0x10, 0x62, 0x21]) + b'LOREM\0\0\0' + size.to_bytes(2, 'little') +
            (24).to_bytes(2, 'little') + size.to_bytes(2, 'little') + (1).to_bytes(2, 'little') +
            text + b'\0\x2b\x2a')


if __name__ == '__main__':
    assert len(TEXT) == 445
    for n in (1, 3, 0, 20):
        m, got = lorem(n)
        expect('N=%d: %d copies, a valid note' % (n, n), got == note(n) and m.shown == ['LOREM CREATED'],
               (len(got) if got else got, m.shown))
    m, got = lorem()
    expect('N missing: 1 copy', got == note(1), len(got) if got else got)
    m, got = lorem(100)
    expect('N=100 needs %d bytes: NOT ENOUGH RAM, nothing created' % (100 * 446 - 1 + 27),
           got is None and m.requested == 100 * 446 - 1 + 27 and m.shown == ['NOT ENOUGH RAM'],
           (m.shown, getattr(m, 'requested', None)))
    m, got = lorem(150)
    expect('N=150 is capped at 100', m.requested == 100 * 446 - 1 + 27, getattr(m, 'requested', None))

    # the QR engine reads it like any note: checking, a first piece, and a piece of copy 2
    content = note(3)
    notes = [('LOREM', content, False)]
    length = 3 * 446 - 1
    m = machine(notes, {'E': 3, 'V': 0, 'M': AUTO}, str2='LOREM')
    expect('engine checks it as %d ASCII characters' % length, m.ans == 2 * length, m.ans)
    m = machine(notes, {'E': 3, 'V': 11, 'N': 321, 'M': AUTO}, str2='LOREM')
    expect('engine encodes the first 321', decode(matrix_from(m, 11))[0].bytes == TEXT[:321])
    m = machine(notes, {'E': 3, 'V': 1, 'N': 11, 'M': AUTO, 'O': 445}, str2='LOREM')
    expect('engine skips into copy 2 (newline, then Lorem ipsu)',
           decode(matrix_from(m, 1))[0].bytes == b'\nLorem ipsu')
    print('\nALL PASSED' if not failures else '\n%d FAILED' % len(failures))
    sys.exit(1 if failures else 0)
