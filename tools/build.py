"""Build and decompile TI-83+ programs for this project.

  python tools/build.py                    build build/QR.8xp and build/QRSRC.8xp from src/,
                                           and the pure-BASIC set src/basic/ -> build/basic/
  python tools/build.py decompile F.8xp    print a program as text (Axe or BASIC, auto-detected)
  python tools/build.py decompile F.8xp -o out.txt

BASIC is tokenized with the tivars library. Axe source is tokenized with the
Axe 1.2.1 token table in tools/axe_tokens.json, because Axe renames many TI
tokens (conj( shows as Copy(, fPart( as float{, the u token as "var", ...).
"""
import json
import struct
import sys
from pathlib import Path

import tivars.models
from tivars import TIProgram, TIRealList
from tivars.types.real import TIReal

ROOT = Path(__file__).resolve().parent.parent

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


def build():
    (ROOT / 'build').mkdir(exist_ok=True)

    # Axe sources: the engine, and LOREMSRC (a test tool that writes a long Notefolio note)
    comments = {'QRSRC': 'QR engine source - compile with Axe',
                'LOREMSRC': 'Lorem ipsum note maker - compile with Axe',
                'SPEEDSRC': '15 MHz speed test - compile with Axe'}
    for path in sorted((ROOT / 'src').glob('*.axe.txt')):
        name = path.name.split('.')[0]
        src = path.read_text(encoding='utf-8').rstrip('\n')
        tokens = axe_tokenize(src)
        back = axe_detokenize(tokens).split('\n')
        changed = [(a, b) for a, b in zip(src.split('\n'), back) if a != b and not a.startswith('.')]
        if changed:
            raise SystemExit('%s: Axe round trip changed code lines: %r' % (path.name, changed[:3]))
        save_program(name, tokens, ROOT / 'build' / (name + '.8xp'), comments.get(name, 'Axe source'))
        print('build/%-11s %5d token bytes' % (name + '.8xp', len(tokens)))

    # BASIC front end
    text = (ROOT / 'src' / 'QR.basic.txt').read_text(encoding='utf-8').rstrip('\n')
    check_spaces('QR.basic.txt', text)
    prog = TIProgram(name='QR')
    prog.load_string(text)
    save_program('QR', bytes(prog.data), ROOT / 'build' / 'QR.8xp', 'QR code menus (BASIC front end)')
    print('build/QR.8xp     %5d token bytes' % len(prog.data))

    # Pure-BASIC generator (the original, cleaned up); its prgmQR collides with the one above.
    # "max" mode keeps tokens inside strings (the r₁ expressions in QRDRAW need them);
    # write \= etc. where a string needs single characters ("<\=>" is <,=,> not ≤,>).
    (ROOT / 'build' / 'basic').mkdir(exist_ok=True)
    for old in [*(ROOT / 'build' / 'basic').glob('*.8x?')]:   # files since merged or renamed
        old.unlink()
    for src in sorted((ROOT / 'src' / 'basic').glob('*.basic.txt')):
        stem = src.name.split('.')[0]               # TI Connect spells θ as _theta_ in file names
        name = stem.replace('_theta_', 'θ')
        prog = TIProgram(name=name)
        text = src.read_text(encoding='utf-8').rstrip('\n')
        check_spaces(src.name, text, 'max')
        prog.load_string(text, mode='max')
        save_program(name, bytes(prog.data), ROOT / 'build' / 'basic' / (stem + '.8xp'),
                     'QR code generator, pure BASIC')
        print('build/basic/%-8s %5d token bytes' % (stem + '.8xp', len(prog.data)))

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
    """build/basic/NAME.8xl: the named real list ʟNAME, in the calculator's own format."""
    lst = TIRealList(name=name)
    lst.load_list([TIReal(v) for v in values])
    lst.raw.name = bytes([0x5D]) + name.encode().ljust(7, bytes(1))   # 5Dh + name, as the calculator writes it
    path = ROOT / 'build' / 'basic' / (name + '.8xl')
    lst.save(str(path))
    finish_8xp(path, comment)
    print('build/basic/%-8s %5d entries' % (name + '.8xl', len(values)))


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
