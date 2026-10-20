"""Engine tests for Str1 text (E=1) and list BIN (E=2).

  python tests/test_engine.py           full sweep (all versions; takes a few minutes)
  python tests/test_engine.py --quick   versions 1, 5, 10 only
  add --standalone to test src/standalone/QRSRC.axe.txt (the QR-only release) instead
  --asm tests the standalone engine's Z80 port (build/standalone/_theta_QR.8xp) instead; it
        runs only the groups its milestones cover so far (docs/asm_port.md)
"""
import random
import sys

from qrtest import (Machine, SRC, ASM, ALNUM_CHARS, CAP_ALNUM, CAP_BYTE, alnum_tokens,
                    ascii_tokens, check_symbol, decode, matrix_from, run_engine,
                    TEXT, BINARY, AUTO, ASCII, ALNUM, BAD, bad)
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
    """Ans of the check-only call (V=0), or (BAD, B) for a bad character."""
    m = run_engine(TEXT, 0, 0, mode, str1=toks)
    return (m.ans, m.get_real('B')) if m.ans == BAD else m.ans


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
    # checking text (V=0): 2*length + 1 if alphanumeric (the mode also goes into M), or BAD
    # with the position in B
    expect('check: auto picks alnum', check_text(alnum_tokens('AB 12'), AUTO) == 2 * 5 + 1)
    expect('check: auto picks ASCII for lowercase', check_text(ascii_tokens('Hello'), AUTO) == 2 * 5)
    expect('check: forced ASCII on alnum text', check_text(alnum_tokens('AB'), ASCII) == 2 * 2)
    expect('check: forced alnum', check_text(alnum_tokens('AB'), ALNUM) == 2 * 2 + 1)
    expect('check: forced alnum, lowercase at 3', check_text(ascii_tokens('ABc'), ALNUM) == bad(3))
    expect('check: forced alnum, first non-alnum wins',
           check_text(ascii_tokens('A!') + [PI], ALNUM) == bad(2))
    expect('check: pi bad in auto', check_text(ascii_tokens('2') + [PI] + ascii_tokens('r'), AUTO) == bad(2))
    expect('check: sin( bad in ASCII', check_text(ascii_tokens('ab') + [SIN], ASCII) == bad(3))
    # two-byte tokens: BB 00 (npv() must not match the second-byte row's zeros; others aren't ASCII
    expect('check: npv( (BB 00) bad', check_text(ascii_tokens('a') + [b'\xbb\x00'], AUTO) == bad(2))
    expect('check: [A] (5C 00) bad', check_text([b'\x5c\x00'] + ascii_tokens('a'), AUTO) == bad(1))
    expect('check: empty text', check_text([], AUTO) == 1)
    # encoding with a bad character fails before drawing
    # the engine never changes M: the caller sets it from the check's Ans
    for label, toks, mode in (('auto, alnum text', alnum_tokens('AB 12'), AUTO),
                              ('auto, lowercase', ascii_tokens('Hello'), AUTO),
                              ('forced ASCII', alnum_tokens('AB'), ASCII),
                              ('forced alnum', alnum_tokens('AB'), ALNUM)):
        c = run_engine(TEXT, 0, 0, mode, str1=toks)
        expect('check, %s: M left at %d' % (label, mode), c.get_real('M') == mode, c.get_real('M'))
    m = Machine(SRC)
    for name, val in zip('EV', (TEXT, 0)):
        m.set_real(name, val)
    m.set_str(1, b''.join(alnum_tokens('AB')))
    m.run()
    expect('check with no M: auto, nothing stored', m.ans == 2 * 2 + 1 and ('real', 'M') not in m.os, m.ans)

    def draw_auto(toks, **extra):
        """A draw call in auto mode with no check first (V=1, M=0)."""
        m = Machine(SRC)
        for name, val in {'E': TEXT, 'V': 1, 'N': 17, 'M': AUTO, 'O': 0, 'B': 0, **extra}.items():
            m.set_real(name, val)
        m.set_str(1, b''.join(toks))
        m.run()
        return m
    m = draw_auto(alnum_tokens('ABC'))
    expect('draw, auto, no check: decides alnum itself, M left at 0',
           m.ans == 0 and check_symbol(m, 1, 'ABC', 'alphanumeric') is not None and m.get_real('M') == 0)
    m = draw_auto(ascii_tokens('abc'), A=1)
    expect('draw, auto, no check: lowercase is ASCII; a leftover A=1 is ignored',
           m.ans == 0 and check_symbol(m, 1, 'abc', 'byte') is not None and m.get_real('M') == 0)
    m = draw_auto(ascii_tokens('a') + [PI])
    expect('draw, auto, no check: a bad character fails, nothing drawn', (m.ans, m.get_real('B')) == bad(2) and not m.displays, m.ans)
    expect('encode: auto, lowercase -> byte mode', drawn(ascii_tokens('Hi there'), AUTO) == (0, b'Hi there'))
    expect('encode: forced ASCII on alnum text', drawn(alnum_tokens('ABC'), ASCII) == (0, b'ABC'))
    expect('encode: forced alnum', drawn(alnum_tokens('ABC 1'), ALNUM) == (0, b'ABC 1'))
    m = run_engine(TEXT, 1, 3, ASCII, str1=alnum_tokens('ABC'))
    expect('forced ASCII really uses byte mode', m.ans == 0 and check_symbol(m, 1, 'ABC', 'byte'))
    # special characters
    expect('ascii: real quote token',
           drawn(ascii_tokens('say ') + [Q] + ascii_tokens('hi') + [Q], AUTO) == (0, b'say "hi"'))
    # the negative sign ⁻ isn't ASCII (only the minus sign is): a bad character in every mode
    for label, toks, mode, pos in (('auto', ascii_tokens('x=') + [NEG] + ascii_tokens('5'), AUTO, 3),
                                   ('ASCII', ascii_tokens('x=') + [NEG] + ascii_tokens('5'), ASCII, 3),
                                   ('alnum', alnum_tokens('A') + [NEG] + alnum_tokens('1'), ALNUM, 2)):
        expect('%s: negative sign is a bad character at %d' % (label, pos), check_text(toks, mode) == bad(pos),
               check_text(toks, mode))
    toks = ascii_tokens('x=') + [NEG] + ascii_tokens('5')
    expect('auto draw with no check: negative sign fails, nothing drawn', drawn(toks, AUTO) == (65533, None),
           drawn(toks, AUTO))
    expect('ascii: minus sign still encodes', drawn(ascii_tokens('x-5'), AUTO) == (0, b'x-5'))
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
    expect('only E, V, N: auto (M=0) decides alnum itself, from the start (O=0); no M to store in',
           m.ans == 0 and check_symbol(m, 1, 'AB12', 'alphanumeric') is not None and ('real', 'M') not in m.os)
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


def asm_stub():
    """Milestone 1 of the Z80 port: the stub only sets 15 MHz where there is one and Ans = 0."""
    m = Machine(SRC)
    m.run()
    expect('asm: returns Ans = 0', m.ans == 0, m.ans)
    expect('asm: 15 MHz on a TI-84+', m.full)
    m = Machine(SRC, model='83+')
    m.run()
    expect('asm: a TI-83+ keeps its speed port alone, Ans = 0', m.ans == 0 and not m.full, m.ans)


if __name__ == '__main__':
    if ASM:        # the groups below join as the port's milestones reach them
        asm_stub()
    else:
        edge_cases()
        skipping()
        sweep([1, 5, 10] if '--quick' in sys.argv else range(1, 12))
    print('\n%s' % ('ALL PASSED' if not failures else '%d FAILED' % len(failures)))
    sys.exit(1 if failures else 0)
