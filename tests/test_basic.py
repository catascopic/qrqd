"""Tests for the pure-BASIC generator (src/QRBASIC.basic.txt and src/_theta_QRBIT.basic.txt,
built into build/ next to the hybrid's files).

The programs run in tibasic, the user's TI-BASIC emulator (expected in ../tibasic; set
TIBASIC to its path otherwise).
prgmQRBASIC is driven through its menus with scripted choices and Input text, and the
graph screen is compared with the `qrcode` reference and decoded, as in qrtest.py.
(--originals runs the original prgmQR/QRCW/QRBIT/QRECC/QRDRAW, which center by default.)

  python tools/build.py && python tests/test_basic.py           all versions
  python tools/build.py && python tests/test_basic.py --quick   versions 1, 6, 10
  python tests/test_basic.py --originals                        run originals/ instead

Timing means nothing here: the interpreter is not a calculator.
"""
import io
import os
import random
import sys
from pathlib import Path

from qrtest import ROOT, ALNUM_CHARS, CAP_ALNUM, CAP_BYTE, decode, reference

sys.path.append(os.environ.get('TIBASIC', str(ROOT.parent / 'tibasic')))
import tifile                                     # noqa: E402
from core import TiList                           # noqa: E402
from environment import Environment               # noqa: E402
from terminal import ScriptedConsole              # noqa: E402
from catalog import get_token, CHAR_TABLE         # noqa: E402
from core import TiString                         # noqa: E402

sys.path.insert(0, str(ROOT / 'tools'))
from build import TIProgram                       # noqa: E402  (with the π fix)

PROGRAMS = ROOT / ('originals' if '--originals' in sys.argv else 'build')
DATA = ROOT / 'tests' / 'data' / 'basic'          # ʟGFL, ʟGFX from the user's calculator
ASCII, ALNUM, BINARY, SET_VERSION, OPTIONS, REDRAW, EXIT = range(7)   # main menu choices
STOREPIC, ALT_PUNCT, ASCII_FIX, XOR_TABLE, BACK = range(5)      # options menu
SKIPPED = {5: 6, 9: 10}   # an automatic pick bumps these to the next (faster) one; set ones are kept
ORIGINALS = '--originals' in sys.argv
if ORIGINALS:
    ALNUM, ASCII = 0, 1                           # the originals' menu lists Alphanumeric first

failures = []


def expect(name, cond, detail=''):
    print(('ok    ' if cond else 'FAIL  ') + name + ('' if cond else '  ' + str(detail)))
    if not cond:
        failures.append(name)


def install(env, name, tokens_bytes):
    stream = io.BytesIO(len(tokens_bytes).to_bytes(2, 'little') + tokens_bytes)
    tifile.ProgramFile(name, tifile._read_token_stream(stream)).store_to(env)


class TokenConsole(ScriptedConsole):
    """Also takes an input as a list of tokens (for π, which is a key, not a character)."""
    def _input(self, prompt):
        if self.inputs and isinstance(self.inputs[0], list):
            return self.inputs.pop(0)
        return super()._input(prompt)


def run_qr(choices, inputs, center=1, binary=None, patch=None, str3=None, cw=None):
    """Run prgmQRBASIC (or the original prgmQR). `patch` maps program name ->
    function(text) -> text for variants. `center` only exists in the originals."""
    env = Environment(console=TokenConsole(inputs=inputs, choices=choices))
    # ʟGFL, ʟGFX (and ʟXOR) as built for sending; the originals use the calculator's copies
    if ORIGINALS:
        tifile.load_environment(env, DATA)
        files = list(PROGRAMS.glob('*.8xp'))
    else:                                 # build/ also holds the hybrid's files
        for name in ('GFL', 'GFX', 'XOR'):
            tifile._READERS['.8xl'].load(PROGRAMS / (name + '.8xl')).store_to(env)
        files = [PROGRAMS / 'QRBASIC.8xp', PROGRAMS / '_theta_QRBIT.8xp']
    for f in files:
        data = bytes(TIProgram.open(str(f)).data)
        name = f.stem.replace('_theta_', 'θ')   # the file name spells θ as _theta_
        if patch and name in patch:     # from the source: decompiled text loses its escapes
            src = (ROOT / 'src' / (f.stem + '.basic.txt')).read_text(encoding='utf-8')
            p = TIProgram(name=name)
            p.load_string(patch[name](src).rstrip('\n'), mode='max')
            data = bytes(p.data)
        install(env, name, data)
    if ORIGINALS:
        env.user_lists['QR'] = TiList([float(center), 1.0, 0.0, 0.0, 0.0])
    if binary is not None:
        env.user_lists['BIN'] = TiList([float(b) for b in binary])
    if str3 is not None:
        env.strings[2] = TiString(str3)
    if cw is not None:
        env.user_lists['CW'] = TiList([float(x) for x in cw])
    env.submit([get_token(0x5F), *(CHAR_TABLE[c] for c in ('QR' if ORIGINALS else 'QRBASIC'))])
    return env


def symbol(env, version, center):
    S = 17 + 4 * version
    center = center and ORIGINALS            # QRBASIC always draws at the top left
    G = 31 - S // 2 if center else 0
    H = 47 - S // 2 if center else 0
    mat = [[int(env.graph.get(G + y, H + x)) for x in range(S)] for y in range(S)]
    lit = sum(env.graph.get(r, c) for r in range(64) for c in range(96))
    assert lit == sum(map(sum, mat)), 'stray pixels'
    return mat


def check(name, env, version, center, payload, mode):
    try:
        mat = symbol(env, version, center)
        assert mat == reference(payload, version, mode), 'differs from reference encoder'
        got = decode(mat)
        want = payload.encode() if isinstance(payload, str) else bytes(payload)
        assert got and got[0].bytes == want, 'decoded %r' % (got[0].bytes if got else None)
    except AssertionError as e:
        expect(name, False, e)
        return False
    return True


def encode(mode, version, payload, center=1, patch=None):
    v = str(version)
    if mode == BINARY:
        return run_qr([SET_VERSION, BINARY], [v], center, binary=payload, patch=patch)
    return run_qr([SET_VERSION, mode], [v, payload], center, patch=patch)


def payloads(mode, cap):
    rnd = random.Random(cap * 3 + mode)
    for L in sorted({1, 2, 3, cap // 2, cap - 1, cap, rnd.randint(1, cap)}):
        if mode == ALNUM:
            yield ''.join(rnd.choice(ALNUM_CHARS) for _ in range(L))
        elif mode == ASCII:   # the original's ASCII table has π in place of "
            yield ''.join(rnd.choice([chr(c) for c in range(32, 127) if c != 34]) for _ in range(L))
        else:
            yield bytes(rnd.randint(0, 255) for _ in range(L))


def sweep(versions, patch=None, label=''):
    n = 0
    for v in versions:
        drawn = v if patch or not ORIGINALS else SKIPPED.get(v, v)   # the sweep sets the version
        for mode in (ALNUM, ASCII, BINARY):
            cap = (CAP_ALNUM if mode == ALNUM else CAP_BYTE)[v - 1]
            for p in payloads(mode, cap):
                for center in ((0, 1) if len(p) == cap and ORIGINALS else (1,)):
                    name = '%sv%d mode %d length %d center %d' % (label, v, mode, len(p), center)
                    env = encode(mode, v, p, center, patch)
                    if not check(name, env, drawn, center, p, 'alphanumeric' if mode == ALNUM else 'byte'):
                        return n
                    n += 1
    expect('%s%d symbols match the reference encoder and decode' % (label, n), True)
    return n


def screens(env):
    return '\n'.join(env.console.frames) + '\n' + str(env.home)


def edge_cases():
    # too long for the set version: truncated, with a note on the Encoding screen
    # (25 is odd, so the last character goes alone in 6 bits)
    msg = 'HELLO WORLD 0123456789 ABCDEFGH'
    env = run_qr([SET_VERSION, ALNUM], ['1', msg])
    expect('truncate to an odd length', check('truncate', env, 1, 0, msg[:25], 'alphanumeric'))
    expect('truncation note: 25 of 31 chars encoded',
           '25 of 31' in screens(env) and 'chars encoded' in screens(env), screens(env))
    env = run_qr([SET_VERSION, BINARY], ['1'], binary=list(range(20)))
    expect('truncated ʟBIN: 17 of 20 bytes encoded',
           check('truncate list', env, 1, 0, bytes(range(17)), 'byte') and
           '17 of 20' in screens(env) and 'bytes encoded' in screens(env), screens(env))
    env = run_qr([ALNUM], ['HELLO'])
    expect('no note when it fits', 'encoded' not in screens(env), screens(env))
    # auto version: the smallest that fits, skipping 9 always and 5 with the XOR table off
    # (the user's timings: with the table, 5 is faster than 6; 9 stays slower than 10)
    env = run_qr([ALNUM], ['A' * 120])
    expect('120 alphanumeric chars, table off: version 6 (not 5)', check('auto v6', env, 6, 0, 'A' * 120, 'alphanumeric'))
    env = run_qr([OPTIONS, XOR_TABLE, BACK, ALNUM], ['A' * 120])
    expect('120 alphanumeric chars, table on: version 5', check('auto v5', env, 5, 0, 'A' * 120, 'alphanumeric'))
    env = run_qr([OPTIONS, XOR_TABLE, BACK, ALNUM], ['A' * 300])
    expect('300 alphanumeric chars, table on: still version 10 (not 9)', check('auto v10 table', env, 10, 0, 'A' * 300, 'alphanumeric'))
    # versions 5 and 9: drawn when set, whatever the automatic pick does
    for v in (5, 9):
        env = run_qr([SET_VERSION, ALNUM], [str(v), 'HELLO 5 AND 9'])
        expect('set version %d is drawn as %d' % (v, v), check('set v%d' % v, env, v, 0, 'HELLO 5 AND 9', 'alphanumeric'))
    env = run_qr([ALNUM], ['A' * 300])
    expect('300 alphanumeric chars: version 10 (not 9)', check('auto v10', env, 10, 0, 'A' * 300, 'alphanumeric'))
    # cleanup: L₁-L₅ emptied (still defined) at the end; ʟCW kept for Redraw, and Str2 kept
    # (the working table: handy when testing)
    def cleaned(env):
        return ([env.lists[k] is not None and len(env.lists[k].data) == 0 for k in range(5)] == [True] * 5
                and len(env.user_lists['CW'].data) > 0)
    for label, choices in (('XOR table off', [ALNUM]), ('XOR table on', [OPTIONS, XOR_TABLE, BACK, ALNUM])):
        env = run_qr(choices, ['A' * 120])
        table = str(env.strings[1]) if env.strings[1] is not None else None
        expect('cleanup after drawing (%s): L1-L5 empty, CW and Str2 (alnum table) kept' % label,
               cleaned(env) and table is not None and table.startswith('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ '),
               ([None if l is None else len(l.data) for l in env.lists[:5]], table))
    # Redraw: draws whatever ʟCW holds (the version from its length)
    for v in (2, 7):
        msg = 'REDRAW TEST %d' % v
        first = run_qr([SET_VERSION, ALNUM], [str(v), msg])
        cw = [x for x in first.user_lists['CW'].data]
        env = run_qr([REDRAW], [], cw=cw)
        same = all(env.graph.get(r, c) == first.graph.get(r, c) for r in range(64) for c in range(96))
        expect('Redraw v%d from ʟCW (%d elements): same code, cleaned up' % (v, len(cw)),
               same and check('redraw v%d' % v, env, v, 0, msg, 'alphanumeric') and cleaned(env), same)
    # a bad character: error with the character and position, back to the menu, nothing drawn
    for mode, text, pos, ch in ((ALNUM, 'ABcD', 3, 'c'), (ASCII, 'ab' + 'θ' + 'c', 3, 'θ')):
        try:
            env = run_qr([mode, EXIT], [text])
            lit = sum(env.graph.get(r, c) for r in range(64) for c in range(96))
            sc = screens(env)
            ok = 'ERR:BAD CHAR' in sc and 'Pos=%d' % pos in sc and lit == 0
            ok = ok and (ch is None or 'Char: ' + ch in sc)
            expect('bad char in mode %d at %d: error, nothing drawn' % (mode, pos), ok, (lit, sc))
        except Exception as e:
            expect('bad char in mode %d' % mode, False, repr(e))
    # alt punct: ? ; ' , - . ! : type in place of $ % * + - . / :
    env = run_qr([OPTIONS, ALT_PUNCT, BACK, ALNUM], ["HI?;'!"])
    expect("alt punct: HI?;'! scans as HI$%*/", check('alt punct', env, 1, 0, 'HI$%*/', 'alphanumeric'))
    # ASCII: π stands in for the quote
    # ASCII fix: a 95-character Str3 of your own (here with a real quote) is used as the table
    table = [CHAR_TABLE[chr(c)] for c in range(32, 127)]
    env = run_qr([OPTIONS, ASCII_FIX, BACK, ASCII], ['say "hi"'], str3=table)
    expect('ASCII fix: a real " through a custom Str3', check('ascii fix', env, 1, 0, 'say "hi"', 'byte'))
    pi = get_token(0xAC)
    env = run_qr([ASCII], [[*(CHAR_TABLE[c] for c in 'say '), pi, CHAR_TABLE['h'], CHAR_TABLE['i'], pi]])
    expect('ASCII: π encodes as "', check('pi quote', env, 1, 0, 'say "hi"', 'byte'))


def gf_tables():
    """build/GFL.8xl and GFX.8xl must equal the lists saved from the user's calculator
    (tests/data/basic), apart from the header comment."""
    for name in ('GFL', 'GFX'):
        built, saved = (PROGRAMS / (name + '.8xl')).read_bytes(), (DATA / (name + '.8xl')).read_bytes()
        expect("%s.8xl matches the calculator's ʟ%s" % (name, name),
               built[:11] + built[53:] == saved[:11] + saved[53:])


def xor_table():
    """build/XOR.8xl: the named list ʟXOR, entry 16a+b+1 = a xor b, in the calculator's
    own list format (same header layout as ʟGFL/ʟGFX saved from the calculator). With the
    "XOR table" option on, both XORs in the ECC use it; versions 1, 7 and 10 cover 1, 2 and 4
    blocks (v10 has long blocks too). The sweep covers the option off (the default)."""
    from tivars import TIRealList
    path = PROGRAMS / 'XOR.8xl'
    values = [int(float(x)) for x in TIRealList.open(str(path)).list()]
    b, g = path.read_bytes(), (DATA / 'GFL.8xl').read_bytes()
    expect('XOR.8xl is ʟXOR with the 256 nibble XORs',
           values == [a ^ c for a in range(16) for c in range(16)] and b[59:64] == bytes([1, 0x5D]) + b'XOR' and
           b[:11] == g[:11] and b[68:70] == g[68:70], (b[55:74].hex(' '), values[:20]))
    for v, mode in ((1, ALNUM), (7, ASCII), (10, BINARY)):
        cap = (CAP_ALNUM if mode == ALNUM else CAP_BYTE)[v - 1]
        payload = next(p for p in payloads(mode, cap) if len(p) == cap)
        inputs = [str(v)] + ([] if mode == BINARY else [payload])
        env = run_qr([OPTIONS, XOR_TABLE, BACK, SET_VERSION, mode], inputs,
                     binary=payload if mode == BINARY else None)
        if not check('XOR table v%d' % v, env, v, 0, payload, 'alphanumeric' if mode == ALNUM else 'byte'):
            return
    expect('XOR table on: v1, v7, v10 match the reference and decode', True)


if __name__ == '__main__':
    quick = '--quick' in sys.argv
    sweep([1, 6, 10] if quick else range(1, 12))
    if not ORIGINALS:
        edge_cases()
        gf_tables()
        xor_table()
    print('\nALL PASSED' if not failures else '\n%d FAILED' % len(failures))
    sys.exit(1 if failures else 0)
