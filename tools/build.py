"""Build and decompile TI-83+ programs for this project.

  python tools/build.py                    build build/QR.8xp and build/QRSRC.8xp from src/,
                                           and the pure-BASIC set (QRBASIC, θQRBIT, ʟGFL/ʟGFX/ʟXOR);
                                           standalone/src/ (the QR-only release, same program
                                           names) goes to build/standalone/
  python tools/build.py decompile F.8xp    print a program as text (Axe or BASIC, auto-detected)
  python tools/build.py decompile F.8xp -o out.txt

BASIC is tokenized with the tivars library. Axe source is tokenized with the
Axe 1.2.1 token table in tools/axe_tokens.json, because Axe renames many TI
tokens (conj( shows as Copy(, fPart( as float{, the u token as "var", ...).
"""
import json
import shutil
import struct
import sys
from pathlib import Path

import tivars.models
from tivars import TIProgram, TIRealList
from tivars.types.real import TIReal

ROOT = Path(__file__).resolve().parent.parent
MONOCHROME = {'TI-82', 'TI-83', 'TI-83+', 'TI-83+SE', 'TI-84+', 'TI-84+SE'}   # BASIC tokens must exist here
MAX_MODE = {'QRBASIC', 'θQRBIT'}               # BASIC programs tokenized in tivars "max" mode
BASIC_COMMENTS = {'QR': 'QR code menus (BASIC front end)',
                  'QRBASIC': 'QR code generator, pure BASIC',
                  'θQRBIT': 'QR code generator, pure BASIC'}

# tivars 1.1.1 decompiles the π token (ACh) as "π" but only accepts "pi" when tokenizing,
# and "pi" inside a string becomes two lowercase letters. Teach every model's trie "π".
for _model in (v for k, v in vars(tivars.models).items() if k.startswith('TI_')):
    for _trie in _model.tokens.tries.values():
        _trie.children.setdefault('π', type(_trie)()).token = _model.tokens.bytes[b'\xac']
TWO_BYTE = {0x5C, 0x5D, 0x5E, 0x60, 0x61, 0x62, 0x63, 0x7E, 0xAA, 0xBB, 0xEF}

_entries = json.load(open(ROOT / 'tools' / 'axe_tokens.json', encoding='utf-8'))
ENC, DEC = {}, {}
for e in _entries:
    b = bytes(int(x, 16) for x in e['bytes'])
    if e['string']:
        DEC[b] = e['string']
    for s in [e['string']] + e['alts']:
        if s:
            ENC[s] = b
MAXLEN = max(map(len, ENC))


def axe_tokenize(text):
    """Greedy longest-match tokenization, the same way the calculator's editor stores tokens."""
    out, i = bytearray(), 0
    while i < len(text):
        if text[i] == '\n':
            out.append(0x3F); i += 1; continue
        for n in range(min(MAXLEN, len(text) - i), 0, -1):
            if text[i:i + n] in ENC:
                out += ENC[text[i:i + n]]; i += n; break
        else:
            raise ValueError('no Axe token for %r (line %d)' % (text[i:i + 12], text.count('\n', 0, i) + 1))
    return bytes(out)


def axe_detokenize(data):
    out, i = [], 0
    while i < len(data):
        if data[i] == 0x3F:
            out.append('\n'); i += 1; continue
        n = 2 if data[i] in TWO_BYTE else 1
        out.append(DEC[data[i:i + n]]); i += n
    return ''.join(out)


def finish_8xp(path, comment):
    """Match the header style of files saved by TI Connect: product ID 0, readable comment."""
    b = bytearray(path.read_bytes())
    b[10] = 0x00
    c = comment.encode('ascii')[:42]
    b[11:53] = c + bytes(42 - len(c))
    path.write_bytes(b)
    # structural self-check
    dlen = struct.unpack_from('<H', b, 53)[0]
    data = bytes(b[55:55 + dlen])
    assert b[:11] == b'**TI83F*\x1a\x0a\x00' and len(b) == 57 + dlen
    assert sum(data) & 0xFFFF == struct.unpack_from('<H', b, 55 + dlen)[0], 'checksum'


def check_spaces(name, text, mode=None):
    """tivars spells some commands with a trailing space ("Pause ", "FnOff "). Without it they
    tokenize as letters, which can still be valid BASIC (F*n*O*f*f), so refuse to build."""
    for k, line in enumerate(text.split('\n'), 1):
        a, b = TIProgram(name='T'), TIProgram(name='T')
        a.load_string(line, mode=mode)
        b.load_string(line + ' ', mode=mode)
        if len(b.data) < len(a.data):
            raise SystemExit('%s line %d: %r needs a trailing space' % (name, k, line))


def save_program(name, tokens, path, comment):
    prog = TIProgram(name=name)
    prog.data = tokens
    prog.save(str(path))
    finish_8xp(path, comment)
    assert bytes(TIProgram.open(str(path)).data) == tokens


AXE_COMMENTS = {'QRSRC': 'QR engine source - compile with Axe',
                'LOREMSRC': 'Lorem ipsum note maker - compile with Axe',
                'SPEEDSRC': '15 MHz speed test - compile with Axe',
                'NOTESSRC': 'Notefolio picker source - compile with Axe'}


def build():
    (ROOT / 'build').mkdir(exist_ok=True)
    shutil.rmtree(ROOT / 'build' / 'basic', ignore_errors=True)   # where the pure-BASIC set used to go
    build_programs(ROOT / 'src', ROOT / 'build')
    # the QR-only release (old engine with E=4 listing, BASIC note pager): same program names
    (ROOT / 'build' / 'standalone').mkdir(exist_ok=True)
    build_programs(ROOT / 'standalone' / 'src', ROOT / 'build' / 'standalone')
    build_lists()


def build_programs(srcdir, outdir):
    shown = outdir.relative_to(ROOT).as_posix() + '/'
    # Axe sources: the engine, the note picker, and test tools (LOREMSRC, SPEEDSRC)
    for path in sorted(srcdir.glob('*.axe.txt')):
        name = path.name.split('.')[0]
        src = path.read_text(encoding='utf-8').rstrip('\n')
        tokens = axe_tokenize(src)
        back = axe_detokenize(tokens).split('\n')
        changed = [(a, b) for a, b in zip(src.split('\n'), back) if a != b and not a.startswith('.')]
        if changed:
            raise SystemExit('%s: Axe round trip changed code lines: %r' % (path.name, changed[:3]))
        save_program(name, tokens, outdir / (name + '.8xp'), AXE_COMMENTS.get(name, 'Axe source'))
        print('%-28s %5d token bytes' % (shown + name + '.8xp', len(tokens)))

    # BASIC programs: the hybrid's front end (prgmQR) and the pure-BASIC generator (prgmQRBASIC
    # + prgmθQRBIT). The pure-BASIC ones use "max" mode, which keeps tokens inside strings (the
    # r₁ expressions in the drawing need them); they write \= etc. where a string needs single
    # characters ("<\=>" is <,=,> not ≤,>). File names spell θ as _theta_ (TI Connect's way).
    for src in sorted(srcdir.glob('*.basic.txt')):
        stem = src.name.split('.')[0]
        name = stem.replace('_theta_', 'θ')
        mode = 'max' if name in MAX_MODE else None
        text = src.read_text(encoding='utf-8').rstrip('\n')
        check_spaces(src.name, text, mode)
        prog = TIProgram(name=name)
        prog.load_string(text, mode=mode)
        # max munch can pick a token the user's TI-84+ lacks ("Redraw" -> the CE color Red)
        if prog.get_min_os().model not in MONOCHROME:
            raise SystemExit('%s needs a %s token; escape it with \\ (like R\\edraw)'
                             % (src.name, prog.get_min_os().model))
        save_program(name, bytes(prog.data), outdir / (stem + '.8xp'), BASIC_COMMENTS[name])
        print('%-28s %5d token bytes' % (shown + stem + '.8xp', len(prog.data)))


def build_lists():
    # Lists QRBASIC expects on the calculator (sent once): the GF(256) tables (polynomial 11Dh)
    # ʟGFL(n) = log n and ʟGFX(k) = 2^(k-1), and ʟXOR, entry 16a+b+1 = a xor b (4-bit a, b)
    exp = [1]
    for _ in range(254):
        exp.append(exp[-1] * 2 ^ (0x11D if exp[-1] >= 128 else 0))
    log = {x: k for k, x in enumerate(exp)}
    save_list('GFL', [log[n] for n in range(1, 256)], 'GF(256) logs for QRBASIC')
    save_list('GFX', exp, 'GF(256) powers of 2 for QRBASIC')
    save_list('XOR', [a ^ b for a in range(16) for b in range(16)], 'XOR nibble table for QRBASIC')


def save_list(name, values, comment):
    """build/NAME.8xl: the named real list ʟNAME, in the calculator's own format."""
    lst = TIRealList(name=name)
    lst.load_list([TIReal(v) for v in values])
    lst.raw.name = bytes([0x5D]) + name.encode().ljust(7, bytes(1))   # 5Dh + name, as the calculator writes it
    path = ROOT / 'build' / (name + '.8xl')
    lst.save(str(path))
    finish_8xp(path, comment)
    print('%-28s %5d entries' % ('build/' + name + '.8xl', len(values)))


def decompile(path, out=None):
    prog = TIProgram.open(str(path))
    data = bytes(prog.data)
    if data[:1] == b'\x3a':          # Axe sources start with a "." header line
        text = axe_detokenize(data)
    else:
        text = prog.string()
    if out:
        Path(out).write_text(text.rstrip('\n') + '\n', encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'decompile':
        out = sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv else None
        decompile(sys.argv[2], out)
    else:
        build()
