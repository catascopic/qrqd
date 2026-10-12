"""Tests for UNPROSRC (src/UNPROSRC.axe.txt), the tool that unprotects a program so TI
Connect can copy it off the calculator.

UNPROT runs in axesim with a VAT holding programs, appvars and a list. Only the named
program's type byte may change (06h → 05h, flag bits kept). The simulator's VAT names are
latin-1, so "[" (5Bh) stands in for θ, which is the same byte.

  python tests/test_unprot.py
"""
import sys

from qrtest import ROOT, Machine

SRC = (ROOT / 'src' / 'UNPROSRC.axe.txt').read_text(encoding='utf-8')
PRGM, THETA = 0x5F, 0x5B
VAT = [(0x06, '[QRX', False),     # longer name with the same start
       (0x15, '[QR', False),      # an appvar with the same name
       (0x05, 'QR', False),
       (0x06, '[Q', False),       # shorter name
       (0x01, '\x5dBIN', False)]  # a named list

failures = []


def expect(name, cond, detail=''):
    print(('ok    ' if cond else 'FAIL  ') + name + ('' if cond else '  ' + str(detail)))
    if not cond:
        failures.append(name)


def types(m):
    """Type byte of each VAT entry, in m.vat order (build_vat's layout, from F800h down)."""
    p, out = 0xF800, []
    for typ, name, archived in m.vat:
        out.append(m.mem[p])
        p -= 7 + len(name)
    return out


def unprot(target, str1, extra=()):
    """Run UNPROT with the target program among the others; Str1 = token bytes (or None)."""
    m = Machine(SRC)
    m.vat = VAT[:2] + ([target] if target else []) + VAT[2:] + list(extra)
    m.build_vat()
    if str1 is not None:
        m.set_str(1, str1)
    before = types(m)
    m.run()
    return m, before, types(m)


def changed(before, after):
    return [k for k in range(len(before)) if before[k] != after[k]]


if __name__ == '__main__':
    name = [THETA, ord('Q'), ord('R')]
    m, b, a = unprot((0x06, '[QR', False), name)
    expect('θQR protected: now 05h, nothing else changed',
           m.shown == ['UNPROTECTED'] and changed(b, a) == [2] and a[2] == 0x05, (m.shown, b, a))
    m, b, a = unprot((0x06, '[QR', False), [PRGM] + name)
    expect('prgm in front of the name is skipped', m.shown == ['UNPROTECTED'] and a[2] == 0x05, (m.shown, a))
    m, b, a = unprot((0x26, '[QR', False), name)
    expect('flag bits kept: 26h → 25h', a[2] == 0x25 and changed(b, a) == [2], a)
    m, b, a = unprot((0x05, '[QR', False), name)
    expect('already unprotected: NOT PROTECTED, unchanged', m.shown == ['NOT PROTECTED'] and b == a, (m.shown, a))
    m, b, a = unprot((0x06, '[QR', True), name)
    expect('archived: UNARCHIVE IT, unchanged', m.shown == ['UNARCHIVE IT'] and b == a, (m.shown, a))
    m, b, a = unprot(None, name)
    expect('no such program (only the appvar θQR, θQRX, θQ): NOT FOUND, unchanged',
           m.shown == ['NOT FOUND'] and b == a, (m.shown, a))
    m, b, a = unprot((0x06, 'NOTES', False), [THETA] + [ord(c) for c in 'NOTES'])
    expect('a different name that is not there: NOT FOUND', m.shown == ['NOT FOUND'] and b == a, m.shown)
    m, b, a = unprot((0x06, '[NOTES', False), [THETA] + [ord(c) for c in 'NOTES'])
    expect('θNOTES: UNPROTECTED', m.shown == ['UNPROTECTED'] and a[2] == 0x05 and changed(b, a) == [2], (m.shown, a))
    for label, s in (('missing', None), ('empty', []), ('just prgm', [PRGM])):
        m, b, a = unprot((0x06, '[QR', False), s)
        expect('Str1 %s: PUT NAME IN STR1, unchanged' % label, m.shown == ['PUT NAME IN STR1'] and b == a, m.shown)
    print('\nALL PASSED' if not failures else '\n%d FAILED' % len(failures))
    sys.exit(1 if failures else 0)
