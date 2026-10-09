"""Tests for the pure-BASIC generator (src/basic, built into build/basic).

The programs run in tibasic, the user's TI-BASIC emulator (expected in ../tibasic; set
TIBASIC to its path otherwise).
prgmQR is driven through its menus with scripted choices and Input text, and the
graph screen is compared with the `qrcode` reference and decoded, as in qrtest.py.

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

sys.path.insert(0, str(ROOT / 'tools'))
from build import TIProgram                       # noqa: E402  (with the π fix)

PROGRAMS = ROOT / ('originals' if '--originals' in sys.argv else 'build/basic')
DATA = ROOT / 'tests' / 'data' / 'basic'          # ʟGFL, ʟGFX from the user's calculator
ALNUM, ASCII, BINARY, SET_VERSION = 0, 1, 2, 3    # main menu choices
SKIPPED = {5: 6, 9: 10}                           # versions QRCW bumps to the next one

failures = []


def expect(name, cond, detail=''):
    print(('ok    ' if cond else 'FAIL  ') + name + ('' if cond else '  ' + str(detail)))
    if not cond:
        failures.append(name)


def install(env, name, tokens_bytes):
    stream = io.BytesIO(len(tokens_bytes).to_bytes(2, 'little') + tokens_bytes)
    tifile.ProgramFile(name, tifile._read_token_stream(stream)).store_to(env)


def run_qr(choices, inputs, center=1, binary=None, patch=None):
    """Run prgmQR. `patch` maps program name -> function(text) -> text for variants."""
    env = Environment(console=ScriptedConsole(inputs=inputs, choices=choices))
    tifile.load_environment(env, DATA)
    for f in PROGRAMS.glob('*.8xp'):
        data = bytes(TIProgram.open(str(f)).data)
        if patch and f.stem in patch:   # from the source: decompiled text loses its escapes
            src = (ROOT / 'src' / 'basic' / (f.stem + '.basic.txt')).read_text(encoding='utf-8')
            p = TIProgram(name=f.stem)
            p.load_string(patch[f.stem](src).rstrip('\n'), mode='max')
            data = bytes(p.data)
        install(env, f.stem, data)
    env.user_lists['QR'] = TiList([float(center), 1.0, 0.0, 0.0, 0.0])
    if binary is not None:
        env.user_lists['BIN'] = TiList([float(b) for b in binary])
    env.submit([get_token(0x5F), *(CHAR_TABLE[c] for c in 'QR')])
    return env


def symbol(env, version, center):
    S = 17 + 4 * version
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
        drawn = v if patch else SKIPPED.get(v, v)
        for mode in (ALNUM, ASCII, BINARY):
            cap = (CAP_ALNUM if mode == ALNUM else CAP_BYTE)[v - 1]
            for p in payloads(mode, cap):
                for center in ((0, 1) if len(p) == cap else (1,)):
                    name = '%sv%d mode %d length %d center %d' % (label, v, mode, len(p), center)
                    env = encode(mode, v, p, center, patch)
                    if not check(name, env, drawn, center, p, 'alphanumeric' if mode == ALNUM else 'byte'):
                        return n
                    n += 1
    expect('%s%d symbols match the reference encoder and decode' % (label, n), True)
    return n


def edge_cases():
    # Too long for version 1 -> "Continue" truncates to 25 characters (odd, so the last
    # character is encoded alone in 6 bits; the original used the untruncated string's)
    msg = 'HELLO WORLD 0123456789 ABCDEFGH'
    env = run_qr([SET_VERSION, ALNUM, 1], ['1', msg])
    expect('truncate to an odd length', check('truncate', env, 1, 1, msg[:25], 'alphanumeric'))
    # "Abort" must end cleanly without drawing (the original did Goto 0 -> ERR:LABEL)
    try:
        env = run_qr([SET_VERSION, ALNUM, 2], ['1', msg])
        lit = sum(env.graph.get(r, c) for r in range(64) for c in range(96))
        expect('abort draws nothing', lit == 0, '%d pixels lit' % lit)
    except Exception as e:
        expect('abort draws nothing', False, repr(e))


if __name__ == '__main__':
    quick = '--quick' in sys.argv
    sweep([1, 6, 10] if quick else range(1, 12))
    if '--originals' not in sys.argv:
        # versions 5 and 9 work once QRCW stops skipping them
        sweep([5, 9], patch={'QRCW': lambda t: t.replace('V+(V=5 or V=9→V\n', '')},
              label='unskipped ')
        edge_cases()
    print('\nALL PASSED' if not failures else '\n%d FAILED' % len(failures))
    sys.exit(1 if failures else 0)
