"""Engine tests for modes 0-2 (Str1 text and list BIN).

  python tests/test_engine.py           full sweep (all versions; takes a few minutes)
  python tests/test_engine.py --quick   versions 1, 5, 10 only
"""
import random
import sys

from qrtest import (Machine, SRC, ALNUM_CHARS, CAP_ALNUM, CAP_BYTE, alnum_tokens,
                    ascii_tokens, check_symbol, decode, matrix_from, run_engine)

failures = []


def expect(name, cond, detail=''):
    print(('ok    ' if cond else 'FAIL  ') + name + ('' if cond else '  ' + str(detail)))
    if not cond:
        failures.append(name)


def sweep(versions):
    random.seed(1)
    n = 0
    for v in versions:
        for mode in (0, 1, 2):
            cap = (CAP_ALNUM if mode == 0 else CAP_BYTE)[v - 1]
            for L in sorted({0, 1, 2, 3, cap // 2, cap - 1, cap, random.randint(1, cap)}):
                if mode == 0:
                    p = ''.join(random.choice(ALNUM_CHARS) for _ in range(L))
                elif mode == 1:
                    p = ''.join(chr(random.randint(32, 126)) for _ in range(L))
                else:
                    p = bytes(random.randint(0, 255) for _ in range(L))
                for center in (0, 1):
                    if mode == 0:
                        m = run_engine(0, v, L, center, 1, str1=alnum_tokens(p))
                    elif mode == 1:
                        m = run_engine(1, v, L, center, 1, str1=ascii_tokens(p))
                    else:
                        m = run_engine(2, v, L, center, 1, lst=list(p))
                    try:
                        check_symbol(m, v, center, p, 'alphanumeric' if mode == 0 else 'byte')
                    except AssertionError as e:
                        expect('v%d mode %d length %d center %d' % (v, mode, L, center), False, e)
                        return n
                    n += 1
    expect('%d symbols match the reference encoder and decode' % n, True)
    return n


def text_result(mode, toks, safe, version=2):
    m = run_engine(mode, version, len(toks), 1, safe, str1=toks)
    if m.ans:
        return m.ans, len(m.displays)
    return 0, decode(matrix_from(m, version, 1))[0].bytes


def edge_cases():
    Q, PI, NEG, SIN, LOW_A = b'\x2a', b'\xac', b'\xb0', b'\xc2', b'\xbb\xb0'
    # unsupported characters: Safe mode stops (nothing drawn), otherwise substitutes
    expect('alnum safe: bad char position', text_result(0, alnum_tokens('AB1') + [LOW_A], 1) == (4, 0))
    expect('alnum unsafe: substitute *', text_result(0, alnum_tokens('AB') + [SIN] + alnum_tokens('C'), 0) == (0, b'AB*C'))
    expect('ascii safe: pi is unsupported', text_result(1, ascii_tokens('2') + [PI] + ascii_tokens('r'), 1) == (2, 0))
    expect('ascii unsafe: substitute ?', text_result(1, ascii_tokens('2') + [PI] + ascii_tokens('r'), 0) == (0, b'2?r'))
    # special characters
    expect('ascii: real quote token', text_result(1, ascii_tokens('say ') + [Q] + ascii_tokens('hi') + [Q], 1) == (0, b'say "hi"'))
    expect('ascii: negative sign -> hyphen', text_result(1, ascii_tokens('x=') + [NEG] + ascii_tokens('5'), 1) == (0, b'x=-5'))
    expect('alnum: negative sign -> hyphen', text_result(0, alnum_tokens('A') + [NEG] + alnum_tokens('1'), 1) == (0, b'A-1'))
    # count larger than the message or the capacity is clamped
    m = run_engine(0, 1, 500, 0, 1, str1=alnum_tokens('1' * 30))
    expect('clamp to capacity (v1 alnum = 25)', m.ans == 0 and decode(matrix_from(m, 1, 0))[0].bytes == b'1' * 25)
    m = run_engine(2, 2, 999, 0, 1, lst=list(range(5)))
    expect('clamp to list length', m.ans == 0 and decode(matrix_from(m, 2, 0))[0].bytes == bytes(range(5)))
    # bad parameters or missing variables -> 65535, nothing drawn
    for e, v in ((0, 0), (0, 12), (6, 1)):
        m = Machine(SRC)
        for name, val in zip('EVNCS', (e, v, 0, 1, 1)):
            m.set_real(name, val)
        m.set_str(1, b'')
        m.run()
        expect('E=%d V=%d rejected' % (e, v), m.ans == 65535 and not m.displays)
    m = Machine(SRC)
    for name, val in zip('EVNCS', (0, 1, 1, 1, 1)):
        m.set_real(name, val)
    m.run()
    expect('missing Str1 -> 65535', m.ans == 65535)
    m = Machine(SRC)
    for name, val in zip('EVNCS', (2, 1, 1, 1, 1)):
        m.set_real(name, val)
    m.run()
    expect('missing list BIN -> 65535', m.ans == 65535)


if __name__ == '__main__':
    edge_cases()
    sweep([1, 5, 10] if '--quick' in sys.argv else range(1, 12))
    print('\n%s' % ('ALL PASSED' if not failures else '%d FAILED' % len(failures)))
    sys.exit(1 if failures else 0)
