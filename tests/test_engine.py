"""Engine tests for Str1 text (E=1) and list BIN (E=2).

  python tests/test_engine.py           full sweep (all versions; takes a few minutes)
  python tests/test_engine.py --quick   versions 1, 5, 10 only
"""
import random
import sys

from qrtest import (Machine, SRC, ALNUM_CHARS, CAP_ALNUM, CAP_BYTE, alnum_tokens,
                    ascii_tokens, check_symbol, decode, matrix_from, run_engine,
                    TEXT, BINARY, AUTO, ASCII, ALNUM, BAD)
from axesim import L1                                          # noqa: E402

failures = []


def expect(name, cond, detail=''):
    print(('ok    ' if cond else 'FAIL  ') + name + ('' if cond else '  ' + str(detail)))
    if not cond:
        failures.append(name)


def sweep(versions):
    """Alphanumeric text in auto mode, any ASCII text forced to ASCII, and bytes."""
    random.seed(1)
    n = 0
    for v in versions:
        for kind in ('alnum', 'ascii', 'binary'):
            cap = (CAP_ALNUM if kind == 'alnum' else CAP_BYTE)[v - 1]
            for L in sorted({0, 1, 2, 3, cap // 2, cap - 1, cap, random.randint(1, cap)}):
                if kind == 'alnum':
                    p = ''.join(random.choice(ALNUM_CHARS) for _ in range(L))
                    m = run_engine(TEXT, v, L, AUTO, str1=alnum_tokens(p))
                elif kind == 'ascii':
                    p = ''.join(chr(random.randint(32, 126)) for _ in range(L))
                    m = run_engine(TEXT, v, L, ASCII, str1=ascii_tokens(p))
                else:
                    p = bytes(random.randint(0, 255) for _ in range(L))
                    m = run_engine(BINARY, v, L, AUTO, lst=list(p))
                try:
                    check_symbol(m, v, p, 'alphanumeric' if kind == 'alnum' else 'byte')
                except AssertionError as e:
                    expect('v%d %s length %d' % (v, kind, L), False, e)
                    return n
                n += 1
    expect('%d symbols match the reference encoder and decode' % n, True)
    return n


def check_text(toks, mode):
    """Ans of the check-only call (V=0)."""
    return run_engine(TEXT, 0, 0, mode, str1=toks).ans


def drawn(toks, mode, version=2):
    """(Ans, decoded bytes or None) of an encode call."""
    m = run_engine(TEXT, version, len(toks), mode, str1=toks)
    if m.ans:
        return m.ans, None if not m.displays else 'drawn anyway'
    return 0, decode(matrix_from(m, version))[0].bytes


def skipping():
    """O skips characters (or list elements) before encoding: one piece of a split message."""
    def piece(name, source, mode, skip, count, payload, kind, **kw):
        m = run_engine(source, 2, count, mode, skip=skip, **kw)
        try:
            ok = m.ans == 0 and check_symbol(m, 2, payload, kind) is not None
        except AssertionError as e:
            ok = e
        expect(name, ok is True, ok)
    text = 'Hello, World! abc'                     # lowercase letters are 2-byte tokens
    piece('skip 7 of ASCII text', TEXT, ASCII, 7, 6, 'World!', 'byte', str1=ascii_tokens(text))
    piece('skip 6 of alnum text, odd count', TEXT, AUTO, 6, 5, 'WORLD', 'alphanumeric',
          str1=alnum_tokens('HELLO WORLD 123'))
    piece('skip 5 list elements', BINARY, AUTO, 5, 4, bytes(range(5, 9)), 'byte', lst=list(range(20)))
    piece('count past the end stops at the end', TEXT, ASCII, 5, 10, 'FG', 'byte',
          str1=ascii_tokens('ABCDEFG'))
    piece('skip past the end gives an empty code', TEXT, ASCII, 100, 10, '', 'byte',
          str1=ascii_tokens('ABCDEFG'))


def edge_cases():
    Q, PI, NEG, SIN = b'\x2a', b'\xac', b'\xb0', b'\xc2'
    # checking text (V=0): 2*length + 1 if it will be alphanumeric, or BAD + position
    expect('check: auto picks alnum', check_text(alnum_tokens('AB 12'), AUTO) == 2 * 5 + 1)
    expect('check: auto picks ASCII for lowercase', check_text(ascii_tokens('Hello'), AUTO) == 2 * 5)
    expect('check: forced ASCII on alnum text', check_text(alnum_tokens('AB'), ASCII) == 2 * 2)
    expect('check: forced alnum', check_text(alnum_tokens('AB'), ALNUM) == 2 * 2 + 1)
    expect('check: forced alnum, lowercase at 3', check_text(ascii_tokens('ABc'), ALNUM) == BAD + 3)
    expect('check: forced alnum, first non-alnum wins',
           check_text(ascii_tokens('A!') + [PI], ALNUM) == BAD + 2)
    expect('check: pi bad in auto', check_text(ascii_tokens('2') + [PI] + ascii_tokens('r'), AUTO) == BAD + 2)
    expect('check: sin( bad in ASCII', check_text(ascii_tokens('ab') + [SIN], ASCII) == BAD + 3)
    # two-byte tokens: BB 00 (npv() must not match the second-byte row's zeros; others aren't ASCII
    expect('check: npv( (BB 00) bad', check_text(ascii_tokens('a') + [b'\xbb\x00'], AUTO) == BAD + 2)
    expect('check: [A] (5C 00) bad', check_text([b'\x5c\x00'] + ascii_tokens('a'), AUTO) == BAD + 1)
    expect('check: empty text', check_text([], AUTO) == 1)
    # encoding with a bad character fails before drawing
    # encoding trusts the check: it doesn't rescan the text, auto mode takes A from prgmQR
    m = run_engine(TEXT, 1, 3, AUTO, str1=alnum_tokens('ABC'), alnum=0)
    expect('encode: auto with A=0 uses byte mode, even for alnum text',
           m.ans == 0 and check_symbol(m, 1, 'ABC', 'byte') is not None)
    m = run_engine(TEXT, 1, 3, AUTO, str1=alnum_tokens('ABC'), alnum=1)
    expect('encode: auto with A=1 uses alnum', m.ans == 0 and check_symbol(m, 1, 'ABC', 'alphanumeric') is not None)
    expect('encode: auto, lowercase -> byte mode', drawn(ascii_tokens('Hi there'), AUTO) == (0, b'Hi there'))
    expect('encode: forced ASCII on alnum text', drawn(alnum_tokens('ABC'), ASCII) == (0, b'ABC'))
    expect('encode: forced alnum', drawn(alnum_tokens('ABC 1'), ALNUM) == (0, b'ABC 1'))
    m = run_engine(TEXT, 1, 3, ASCII, str1=alnum_tokens('ABC'))
    expect('forced ASCII really uses byte mode', m.ans == 0 and check_symbol(m, 1, 'ABC', 'byte'))
    # special characters
    expect('ascii: real quote token',
           drawn(ascii_tokens('say ') + [Q] + ascii_tokens('hi') + [Q], AUTO) == (0, b'say "hi"'))
    expect('ascii: negative sign -> hyphen', drawn(ascii_tokens('x=') + [NEG] + ascii_tokens('5'), AUTO) == (0, b'x=-5'))
    expect('alnum: negative sign -> hyphen', check_text(alnum_tokens('A') + [NEG] + alnum_tokens('1'), AUTO) == 7
           and drawn(alnum_tokens('A') + [NEG] + alnum_tokens('1'), AUTO) == (0, b'A-1'))
    # count larger than the message or the capacity is clamped
    # prgmQR keeps N within capacity; a bad N may give a wrong symbol but stays inside L1
    m = Machine(SRC)
    for name, val in zip('EVNMO', (TEXT, 1, 9999, ASCII, 0)):
        m.set_real(name, val)
    m.set_str(1, b''.join(ascii_tokens('x' * 800)))
    beyond = bytes(m.mem[L1 + 714:L1 + 0x800])
    m.run()
    expect('N far over capacity writes nothing past L1', m.ans == 0 and m.displays and
           bytes(m.mem[L1 + 714:L1 + 0x800]) == beyond)
    m = run_engine(BINARY, 2, 999, AUTO, lst=list(range(5)))
    expect('clamp to list length', m.ans == 0 and decode(matrix_from(m, 2))[0].bytes == bytes(range(5)))
    expect('runs at full speed (15 MHz)', getattr(m, 'full', False))
    # bad parameters or missing variables -> 65535, nothing drawn
    for e, v, mode in ((0, 1, 0), (5, 1, 0), (1, 12, 0), (1, 1, 3)):
        m = Machine(SRC)
        for name, val in zip('EVNM', (e, v, 0, mode)):
            m.set_real(name, val)
        m.set_str(1, b'')
        m.run()
        expect('E=%d V=%d M=%d rejected' % (e, v, mode), m.ans == 65535 and not m.displays)
    # a variable that doesn't exist reads as 0 (prgmQR sets them all; another caller might not)
    def bare(**reals):
        m = Machine(SRC)
        for name, val in reals.items():
            m.set_real(name, val)
        m.set_str(1, b''.join(alnum_tokens('AB12')))
        m.run()
        return m
    m = bare()
    expect('no variables at all -> 65535 (E reads as 0)', m.ans == 65535 and not m.displays)
    m = bare(E=TEXT)
    expect('only E: a check (V=0) in auto mode (M=0)', m.ans == 2 * 4 + 1, m.ans)
    m = bare(E=TEXT, V=1, N=4)
    expect('only E, V, N: encodes in byte mode (A=0) from the start (O=0)',
           m.ans == 0 and check_symbol(m, 1, 'AB12', 'byte') is not None)
    m = Machine(SRC)
    for name, val in zip('EVNM', (TEXT, 1, 1, AUTO)):
        m.set_real(name, val)
    m.run()
    expect('missing Str1 -> 65535', m.ans == 65535)
    m = Machine(SRC)
    for name, val in zip('EVNM', (BINARY, 1, 1, AUTO)):
        m.set_real(name, val)
    m.run()
    expect('missing list BIN -> 65535', m.ans == 65535)


if __name__ == '__main__':
    edge_cases()
    skipping()
    sweep([1, 5, 10] if '--quick' in sys.argv else range(1, 12))
    print('\n%s' % ('ALL PASSED' if not failures else '%d FAILED' % len(failures)))
    sys.exit(1 if failures else 0)
