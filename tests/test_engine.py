"""Engine tests for Str1 text (E=1), and list BIN (E=2) in the legacy engine.

  python tests/test_engine.py           full sweep (all versions; takes a few minutes)
  python tests/test_engine.py --quick   versions 1, 5, 10 only
  add --legacy to test src/legacy/QRSRC.axe.txt (the older set's engine) instead
  --asm tests the engine's Z80 port (build/_theta_QR.8xp) instead; it
        runs only the groups its milestones cover so far (docs/asm_port.md)
"""
import random
import sys

from qrtest import (Machine, SRC, ASM, ALNUM_CHARS, CAP_ALNUM, CAP_BYTE, alnum_tokens,
                    ascii_tokens, check_symbol, data_codewords, decode, ec_codewords,
                    matrix_from, run_engine, TEXT, BINARY, AUTO, ASCII, ALNUM, BAD, bad)
from axesim import L1, L3                                      # noqa: E402

KINDS = ('alnum', 'ascii') + (('binary',) if BINARY else ())   # ʟBIN: legacy engine only

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
        for kind in KINDS:
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
    if BINARY:
        piece('skip 5 list elements', BINARY, AUTO, 5, 4, bytes(range(5, 9)), 'byte', lst=list(range(20)))
    piece('count past the end stops at the end', TEXT, ASCII, 5, 10, 'FG', 'byte',
          str1=ascii_tokens('ABCDEFG'))
    piece('skip past the end gives an empty code', TEXT, ASCII, 100, 10, '', 'byte',
          str1=ascii_tokens('ABCDEFG'))


Q, PI, NEG, SIN = b'\x2a', b'\xac', b'\xb0', b'\xc2'


def draw_auto(toks, **extra):
    """A draw call in auto mode with no check first (V=1, M=0)."""
    m = Machine(SRC)
    for name, val in {'E': TEXT, 'V': 1, 'N': 17, 'M': AUTO, 'O': 0, 'B': 0, **extra}.items():
        m.set_real(name, val)
    m.set_str(1, b''.join(toks))
    m.run()
    return m


def check_calls():
    """The check call (V=0) and the bad-character answers: no drawing involved."""
    # checking text (V=0): 2*length + 1 if alphanumeric, or BAD with the position in B
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
    m = Machine(SRC)
    for name, val in zip('EVM', (TEXT, 0, ALNUM)):
        m.set_real(name, val)
    m.set_str(1, b''.join(ascii_tokens('ABc')))
    m.run()
    expect('check with no B: still fails at 3, nothing stored', m.ans == BAD and ('real', 'B') not in m.os, m.ans)
    if BINARY:
        m = run_engine(BINARY, 0, 0, AUTO, lst=[65, 200, 0])
        expect('check list BIN: 2 * its length (byte mode)', m.ans == 2 * 3, m.ans)
        m = run_engine(BINARY, 0, 0, ALNUM, lst=[])
        expect('check empty list BIN, M=2 ignored: 0', m.ans == 0, m.ans)
    # the negative sign ⁻ isn't ASCII (only the minus sign is): a bad character in every mode
    for label, toks, mode, pos in (('auto', ascii_tokens('x=') + [NEG] + ascii_tokens('5'), AUTO, 3),
                                   ('ASCII', ascii_tokens('x=') + [NEG] + ascii_tokens('5'), ASCII, 3),
                                   ('alnum', alnum_tokens('A') + [NEG] + alnum_tokens('1'), ALNUM, 2)):
        expect('%s: negative sign is a bad character at %d' % (label, pos), check_text(toks, mode) == bad(pos),
               check_text(toks, mode))
    # a draw call in auto mode with no check scans too: a bad character fails before drawing
    m = draw_auto(ascii_tokens('a') + [PI])
    expect('draw, auto, no check: a bad character fails, nothing drawn', (m.ans, m.get_real('B')) == bad(2) and not m.displays, m.ans)
    toks = ascii_tokens('x=') + [NEG] + ascii_tokens('5')
    expect('auto draw with no check: negative sign fails, nothing drawn', drawn(toks, AUTO) == (65533, None),
           drawn(toks, AUTO))
    m = bare(E=TEXT)
    expect('only E: a check (V=0) in auto mode (M=0)', m.ans == 2 * 4 + 1, m.ans)


def edge_cases():
    m = draw_auto(alnum_tokens('ABC'))
    expect('draw, auto, no check: decides alnum itself, M left at 0',
           m.ans == 0 and check_symbol(m, 1, 'ABC', 'alphanumeric') is not None and m.get_real('M') == 0)
    m = draw_auto(ascii_tokens('abc'), A=1)
    expect('draw, auto, no check: lowercase is ASCII; a leftover A=1 is ignored',
           m.ans == 0 and check_symbol(m, 1, 'abc', 'byte') is not None and m.get_real('M') == 0)
    expect('encode: auto, lowercase -> byte mode', drawn(ascii_tokens('Hi there'), AUTO) == (0, b'Hi there'))
    expect('encode: forced ASCII on alnum text', drawn(alnum_tokens('ABC'), ASCII) == (0, b'ABC'))
    expect('encode: forced alnum', drawn(alnum_tokens('ABC 1'), ALNUM) == (0, b'ABC 1'))
    m = run_engine(TEXT, 1, 3, ASCII, str1=alnum_tokens('ABC'))
    expect('forced ASCII really uses byte mode', m.ans == 0 and check_symbol(m, 1, 'ABC', 'byte'))
    # special characters
    expect('ascii: real quote token',
           drawn(ascii_tokens('say ') + [Q] + ascii_tokens('hi') + [Q], AUTO) == (0, b'say "hi"'))
    expect('ascii: minus sign still encodes', drawn(ascii_tokens('x-5'), AUTO) == (0, b'x-5'))
    # count larger than the message or the capacity is clamped
    # prgmQR keeps N within capacity; a bad N may give a wrong symbol but stays inside L1
    m = Machine(SRC)
    for name, val in zip('EVNMO', (TEXT, 1, 9999, ASCII, 0)):
        m.set_real(name, val)
    m.set_str(1, b''.join(ascii_tokens('x' * 800)))
    end = L1 + (768 if ASM else 714)   # the Z80 port keeps its variables in L₁+714..767, as Axe does
    beyond = bytes(m.mem[end:L1 + 0x800])
    m.run()
    expect('N far over capacity writes nothing past L1', m.ans == 0 and m.displays and
           bytes(m.mem[end:L1 + 0x800]) == beyond)
    if BINARY:
        m = run_engine(BINARY, 2, 999, AUTO, lst=list(range(5)))
        expect('clamp to list length', m.ans == 0 and decode(matrix_from(m, 2))[0].bytes == bytes(range(5)))
    expect('runs at full speed (15 MHz)', getattr(m, 'full', False))
    m = bare(E=TEXT, V=1, N=4)
    expect('only E, V, N: auto (M=0) decides alnum itself, from the start (O=0); no M to store in',
           m.ans == 0 and check_symbol(m, 1, 'AB12', 'alphanumeric') is not None and ('real', 'M') not in m.os)


def bare(**reals):
    """A call with only the given reals (a variable that doesn't exist reads as 0: prgmQR sets
    them all, another caller might not), Str1 = AB12."""
    m = Machine(SRC)
    for name, val in reals.items():
        m.set_real(name, val)
    m.set_str(1, b''.join(alnum_tokens('AB12')))
    m.run()
    return m


def parameter_errors():
    """Bad parameters or a missing input -> 65535, nothing drawn."""
    for e, v, mode in ((0, 1, 0), (4, 1, 0), (1, 12, 0), (1, 1, 3)):
        m = Machine(SRC)
        for name, val in zip('EVNM', (e, v, 0, mode)):
            m.set_real(name, val)
        m.set_str(1, b'')
        m.run()
        expect('E=%d V=%d M=%d rejected' % (e, v, mode), m.ans == 65535 and not m.displays)
    m = bare()
    expect('no variables at all -> 65535 (E reads as 0)', m.ans == 65535 and not m.displays)
    m = Machine(SRC)
    for name, val in zip('EVNM', (TEXT, 1, 1, AUTO)):
        m.set_real(name, val)
    m.run()
    expect('missing Str1 -> 65535', m.ans == 65535)
    if BINARY:
        m = Machine(SRC)
        for name, val in zip('EVNM', (BINARY, 1, 1, AUTO)):
            m.set_real(name, val)
        m.run()
        expect('missing list BIN -> 65535', m.ans == 65535)


def asm_parameters():
    """The Z80 port only: GV's float → integer conversion, archived variables, the speed. (The
    Axe engine's float{ isn't defined for fractions, negatives or values over 65535, so
    axesim refuses those.) A call that gets past the checks doesn't answer 65535."""
    def accepted(**reals):
        return bare(**{'E': TEXT, 'N': 4, 'M': AUTO, **reals}).ans != 65535
    expect('asm: V=11 and M=2 accepted', accepted(V=11, M=2))
    expect('asm: V=256 rejected (not read as its low byte, 0)', not accepted(V=256))
    expect('asm: V=65547 rejected (not wrapped to 11)', not accepted(V=65536 + 11))
    expect('asm: V=10^20 rejected', not accepted(V=10 ** 20))
    expect('asm: V=-1 rejected', not accepted(V=-1))
    expect('asm: V=11.9 accepted (the fraction is dropped)', accepted(V=11.9))
    expect('asm: V=0.5 accepted (reads as 0)', accepted(V=0.5))
    expect('asm: M=2.5 accepted, M=3 not', accepted(M=2.5) and not accepted(M=3))
    expect('asm: E=1.5 is E=1', accepted(E=1.5))
    m = Machine(SRC)
    for name, val in zip('EVNM', (TEXT, 1, 4, AUTO)):
        m.set_real(name, val)
    m.set_str(1, b''.join(alnum_tokens('AB12')), archived=True)
    m.run()
    expect('asm: archived Str1 -> 65535 (like a missing one)', m.ans == 65535, m.ans)
    m = Machine(SRC)
    for name, val in zip('VNM', (1, 4, AUTO)):
        m.set_real(name, val)
    m.set_real('E', TEXT, archived=True)
    m.set_str(1, b''.join(alnum_tokens('AB12')))
    m.run()
    expect('asm: archived E reads as 0 -> 65535', m.ans == 65535, m.ans)
    # FloatToInt on its own: the float at DE -> HL
    wrong = []
    for v in (0, 1, 9, 10, 11, 99, 100, 255, 256, 300, 1234, 9999, 10000, 12345, 32765, 54321,
              65535, 65536, 65537, 99999, 100000, 10 ** 99, 0.5, 0.999, 11.9, 255.5, 65535.9,
              123.456, 1e-5, 1e-99, -1, -0.5, -65535):
        m = Machine(SRC)
        m.mem[L1:L1 + 9] = m.tifloat(v)
        got = m.call('FloatToInt', de=L1).hl
        want = int(v) if 0 <= v < 65536 else 65535
        if got != want:
            wrong.append((v, got, want))
    expect('asm: FloatToInt on 33 values (fractions dropped, negative or > 65535 -> 65535)',
           not wrong, wrong)
    expect('asm: 15 MHz on a TI-84+', bare().full)
    m = Machine(SRC, model='83+')
    m.run()
    expect('asm: a TI-83+ keeps its speed port alone', m.ans == 65535 and not m.full, m.ans)


def asm_codewords(versions):
    """The Z80 port, until it draws: after a draw call, L₁ holds the data codewords and, from
    L₁+330, the EC codewords block after block, compared byte for byte with
    qrtest.data_codewords and ec_codewords (both from the qrcode library). The same payloads
    as sweep(), plus skipping (O) and clamping (N). Nothing may be written between the data
    codewords and L₁+330, or between the EC codewords and the generator at L₁+420."""
    random.seed(1)
    wrong, n = [], 0

    def compare(name, m, payload, v, kind):
        nonlocal n
        ref = data_codewords(payload, v, kind)
        ec = ec_codewords(payload, v, kind)
        got = bytes(m.mem[L1:L1 + len(ref)])
        got_ec = bytes(m.mem[L1 + 330:L1 + 330 + len(ec)])
        if (m.ans != 0 or got != ref or got_ec != ec or any(m.mem[L1 + len(ref):L1 + 330])
                or any(m.mem[L1 + 330 + len(ec):L1 + 420])):
            wrong.append((name, m.ans, got.hex(), ref.hex(), got_ec.hex(), ec.hex()))
        n += 1
    for v in versions:
        for kind in KINDS:
            cap = (CAP_ALNUM if kind == 'alnum' else CAP_BYTE)[v - 1]
            for L in sorted({0, 1, 2, 3, cap // 2, cap - 1, cap, random.randint(1, cap)}):
                if kind == 'alnum':
                    p = ''.join(random.choice(ALNUM_CHARS) for _ in range(L))
                    m = run_engine(TEXT, v, L, AUTO, str1=alnum_tokens(p))
                else:
                    p = ''.join(chr(random.randint(32, 126)) for _ in range(L))
                    m = run_engine(TEXT, v, L, ASCII, str1=ascii_tokens(p))
                compare('v%d %s length %d' % (v, kind, L), m, p,
                        v, 'alphanumeric' if kind == 'alnum' else 'byte')
    for name, args, kw, payload, kind in (
            ('skip 7 of ASCII text', (TEXT, 2, 6, ASCII, ), dict(skip=7, str1=ascii_tokens('Hello, World! abc')), 'World!', 'byte'),
            ('skip 2 lowercase (two-byte) tokens', (TEXT, 2, 3, ASCII), dict(skip=2, str1=ascii_tokens('abcde')), 'cde', 'byte'),
            ('skip 6 of alnum text, odd count', (TEXT, 2, 5, AUTO), dict(skip=6, str1=alnum_tokens('HELLO WORLD 123')), 'WORLD', 'alphanumeric'),
            ('count past the end stops at the end', (TEXT, 2, 10, ASCII), dict(skip=5, str1=ascii_tokens('ABCDEFG')), 'FG', 'byte'),
            ('skip past the end gives no data', (TEXT, 2, 10, ASCII), dict(skip=100, str1=ascii_tokens('ABCDEFG')), '', 'byte'),
            ('version 10: 16-bit byte count', (TEXT, 10, 3, ASCII), dict(str1=ascii_tokens('abc')), 'abc', 'byte'),
            ('version 10: 11-bit alnum count', (TEXT, 10, 3, AUTO), dict(str1=alnum_tokens('A:1')), 'A:1', 'alphanumeric')):
        compare(name, run_engine(*args, **kw), payload, args[1], kind)
    expect('asm: %d sets of data and EC codewords match the reference' % n, not wrong, wrong[:3])


def asm_tables():
    """The Z80 port only: the GF(256) tables in L₃ (exp twice, log) and the generator
    polynomial at L₁+420 (1, then the coefficients as logs) for every EC count used, compared
    with the qrcode library's tables and its generator (the product of (x + 2^i))."""
    from qrcode.base import EXP_TABLE, LOG_TABLE, Polynomial, gexp
    m = Machine(SRC)                   # the drawing reuses L₃ for its map, so call GFTables alone
    m.call('GFTables')
    exp = bytes(EXP_TABLE[:255])
    expect('asm: exp table at L3 (twice) and log table at L3+512',
           bytes(m.mem[L3:L3 + 255]) == exp and bytes(m.mem[L3 + 255:L3 + 510]) == exp
           and bytes(m.mem[L3 + 513:L3 + 768]) == bytes(LOG_TABLE[1:256]))
    wrong = []
    for v, R in enumerate((7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20), 1):
        g = Polynomial([1], 0)
        for i in range(R):
            g = g * Polynomial([1, gexp(i)], 0)
        want = bytes([1] + [LOG_TABLE[g[k]] for k in range(1, R + 1)])
        m = run_engine(TEXT, v, 1, ASCII, str1=ascii_tokens('a'))
        if bytes(m.mem[L1 + 420:L1 + 421 + R]) != want:
            wrong.append(v)
    expect('asm: generator polynomial (as logs) for each version', not wrong, wrong)


def asm_characters():
    """The Z80 port only: CH (Str1 token -> ASCII) on every one-byte token and every BBh
    two-byte token, plus the other two-byte prefixes; AV (ASCII -> alphanumeric value) on
    every byte. Compared with qrtest's tables, which the sweep checks against the reference
    encoder."""
    from qrtest import ASCII_TOK, TWO_BYTE
    want = {t: 32 + k for k, t in enumerate(ASCII_TOK)}
    tokens = ([bytes([b]) for b in range(256) if b not in TWO_BYTE] +
              [bytes([0xBB, b]) for b in range(256)] +
              [bytes([p, b]) for p in sorted(TWO_BYTE - {0xBB}) for b in (0, 1, 0xD2)])
    m = Machine(SRC)
    lab = m.labels
    wrong = []
    for t in tokens:
        m.mem[L3:L3 + 2] = t.ljust(2, b'\x3f')
        m.mem[lab['READPTR']:lab['READPTR'] + 2] = L3.to_bytes(2, 'little')
        m.mem[lab['POS']:lab['POS'] + 2] = (41).to_bytes(2, 'little')
        a = m.call('CH').a
        ptr = int.from_bytes(m.mem[lab['READPTR']:lab['READPTR'] + 2], 'little')
        pos = int.from_bytes(m.mem[lab['POS']:lab['POS'] + 2], 'little')
        if (a, ptr, pos) != (want.get(t, 0), L3 + len(t), 42):
            wrong.append((t.hex(), a, ptr - L3, pos))
    expect('asm: CH on %d tokens (ASCII code or 0, steps past the token, Pos + 1)' % len(tokens),
           not wrong, wrong[:5])
    wrong = []
    for a in range(256):
        cpu = m.call('AV', a=a)
        got = None if cpu.f & 1 else cpu.a
        exp = ALNUM_CHARS.index(chr(a)) if chr(a) in ALNUM_CHARS else None
        if got != exp:
            wrong.append((a, got, exp))
    expect('asm: AV on all 256 bytes (45 alphanumeric values, carry for the rest)', not wrong, wrong[:5])


if __name__ == '__main__':
    versions = [1, 5, 10] if '--quick' in sys.argv else range(1, 12)
    check_calls()
    edge_cases()
    parameter_errors()
    skipping()
    sweep(versions)
    if ASM:        # the Z80 port's own: its routines on their own, its memory, its choices
        asm_parameters()
        asm_characters()
        asm_codewords(versions)
        asm_tables()
    print('\n%s' % ('ALL PASSED' if not failures else '%d FAILED' % len(failures)))
    sys.exit(1 if failures else 0)
