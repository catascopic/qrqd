"""Build and decompile TI-83+ programs for this project.

  python tools/build.py                    build build/QR.8xp and build/QRSRC.8xp from src/,
                                           and the pure-BASIC set (QRBASIC, θQRBIT, ʟGFL/ʟGFX/ʟXOR);
                                           src/standalone/ (the QR-only release, same program
                                           names) goes to build/standalone/; *.z80 sources are
                                           assembled with spasm-ng when it is installed
  python tools/build.py decompile F.8xp    print a program as text (Axe or BASIC, auto-detected;
                                           an assembly program as hex)
  python tools/build.py decompile F.8xp -o out.txt

BASIC is tokenized with the tivars library. Axe source is tokenized with the
Axe 1.2.1 token table in tools/axe_tokens.json, because Axe renames many TI
tokens (conj( shows as Copy(, fPart( as float{, the u token as "var", ...).
"""
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import tivars.models
from tivars import TIProgram, TIRealList
from tivars.types import TIProtectedAsmProgram
from tivars.types.real import TIReal

ROOT = Path(__file__).resolve().parent.parent
TI83P = {'TI-82', 'TI-83', 'TI-83+', 'TI-83+SE'}  # BASIC tokens that run on a TI-83+
TI84P = {'TI-84+', 'TI-84+SE'}                     # allowed, with a warning (TI-84+ only)
MAX_MODE = {'QRBASIC', 'θQRBIT'}               # BASIC programs tokenized in tivars "max" mode
BASIC_COMMENTS = {'QR': 'QR code menus (BASIC front end)',
                  'QRBASIC': 'QR code generator, pure BASIC',
                  'θQRBIT': 'QR code generator, pure BASIC',
                  'XORTEST': 'XOR speed test for QRBASIC'}
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


def strip_axe_comments(name, src):
    """Drop every comment line except the first (the .NAME header that names Axe's output) and
    every blank line: comments only cost RAM on the calculator. Comments are whole lines
    starting with "." (axesim, which runs the sources in the tests, skips the same lines), so
    they may use any characters; a multi-line "..." comment isn't supported here or in axesim."""
    lines = src.split('\n')
    if not lines[0].startswith('.') or lines[0].startswith('..'):
        raise SystemExit('%s: line 1 must be the .NAME header' % name)
    for k, line in enumerate(lines, 1):
        if line.startswith('...'):
            raise SystemExit('%s line %d: "..." comment blocks are not supported' % (name, k))
    return '\n'.join([lines[0]] + [s for s in lines[1:] if s.strip() and not s.startswith('.')])


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


def check_letters(name, text, data):
    """Lowercase letters (tokens BB B0-BB CA) are only valid inside strings. A misspelled
    command ("checkTimer(" for "checkTmr(") still tokenizes, as letters, and would only fail
    on the calculator with ERR:SYNTAX, so refuse to build. A string runs from " to the next
    ", → or end of line."""
    line, in_string, i = 1, False, 0
    while i < len(data):
        b = data[i]
        if b == 0x3F:                      # newline
            line, in_string = line + 1, False
        elif b == 0x2A:                    # "
            in_string = not in_string
        elif b == 0x04:                    # →
            in_string = False
        elif b == 0xBB and not in_string and 0xB0 <= data[i + 1] <= 0xCA and data[i + 1] != 0xBB:
            raise SystemExit('%s line %d: lowercase letters outside a string (a misspelled '
                             'command?): %s' % (name, line, text.split('\n')[line - 1]))
        i += 2 if b in TWO_BYTE else 1


def save_program(name, tokens, path, comment):
    if len(name) > 8:   # tivars would quietly cut it (UNPROTSRC became UNPROTSR)
        raise SystemExit('%s: program names are at most 8 characters' % name)
    prog = TIProgram(name=name)
    prog.data = tokens
    prog.save(str(path))
    finish_8xp(path, comment)
    assert bytes(TIProgram.open(str(path)).data) == tokens


def find_spasm():
    """spasm-ng: tools/spasm/ (gitignored, with ti83plus.inc next to it), else on PATH."""
    local = ROOT / 'tools' / 'spasm' / 'spasm64.exe'
    if local.exists():
        return local
    found = shutil.which('spasm64') or shutil.which('spasm')
    return Path(found) if found else None


def assemble(path, spasm):
    """Assemble a .z80 source to raw bytes, BB 6D (the compiled-assembly header) then code
    from userMem, and its labels: the text of a .lab file ("NAME = $ADDR" lines, names in
    capitals) with only the names the source defines (spasm's lists every equate in
    ti83plus.inc too); the tests call subroutines by name. spasm writes raw binary for a .bin
    output name; it would name an .8xp after the file (_THETA_Q), so the .8xp is written here
    instead."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'out.bin'
        r = subprocess.run([str(spasm), '-N', '-L', '-I', str(spasm.parent), '-I', str(path.parent),
                            str(path), str(out)], capture_output=True, text=True)
        if r.returncode or not out.exists() or 'error' in (r.stdout + r.stderr).lower():
            raise SystemExit('%s: spasm failed\n%s' % (path.name, (r.stdout + r.stderr).strip()))
        data = out.read_bytes()
        labels = out.with_suffix('.lab').read_text(encoding='latin-1').splitlines()
    if data[:2] != b'\xbb\x6d':
        raise SystemExit('%s: must start with .db t2ByteTok, tasmCmp (BB 6D)' % path.name)
    if 0x9D95 + len(data) - 2 > 0xC000:   # code past C000h crashes the calculator
        raise SystemExit('%s: %d bytes of code, at most 8811 can run' % (path.name, len(data) - 2))
    src = path.read_text(encoding='utf-8')
    own = {m.upper() for m in re.findall(r'^([A-Za-z_]\w*)(?::|\s*=)', src, re.M)}
    return data, ''.join(l + '\n' for l in labels if l.split(' = ')[0] in own)


AXE_COMMENTS = {'QRSRC': 'QR engine source - compile with Axe',
                'LOREMSRC': 'Lorem ipsum note maker - compile with Axe',
                'SPEEDSRC': '15 MHz speed test - compile with Axe',
                'NOTESSRC': 'Notefolio picker source - compile with Axe',
                'UNPROSRC': 'Program unprotector - compile with Axe',
                'CHATSRC': 'CodeChat prototype source - compile with Axe'}
ASM_COMMENTS = {'θQR': 'QR engine, Z80 assembly'}   # ASCII only (header comment)


def build():
    (ROOT / 'build').mkdir(exist_ok=True)
    shutil.rmtree(ROOT / 'build' / 'basic', ignore_errors=True)   # where the pure-BASIC set used to go
    (ROOT / 'build' / '83_safe_QRBASIC.8xp').unlink(missing_ok=True)   # the timer-free copy, now QRBASIC
    build_programs(ROOT / 'src', ROOT / 'build')
    # the QR-only release (old engine with E=4 listing, BASIC note pager): same program names
    (ROOT / 'build' / 'standalone').mkdir(exist_ok=True)
    build_programs(ROOT / 'src' / 'standalone', ROOT / 'build' / 'standalone')
    build_lists()


def build_programs(srcdir, outdir):
    shown = outdir.relative_to(ROOT).as_posix() + '/'
    # Axe sources: the engine, the note picker, and test tools (LOREMSRC, SPEEDSRC)
    for path in sorted(srcdir.glob('*.axe.txt')):
        name = path.name.split('.')[0]
        src = strip_axe_comments(path.name, path.read_text(encoding='utf-8').rstrip('\n'))
        tokens = axe_tokenize(src)
        back = axe_detokenize(tokens).split('\n')
        changed = [(a, b) for a, b in zip(src.split('\n'), back) if a != b]
        if changed:
            raise SystemExit('%s: Axe round trip changed code lines: %r' % (path.name, changed[:3]))
        save_program(name, tokens, outdir / (name + '.8xp'), AXE_COMMENTS.get(name, 'Axe source'))
        print('%-32s %5d token bytes' % (shown + name + '.8xp', len(tokens)))

    # Assembly programs (the standalone engine's Z80 port), when spasm-ng is installed
    asm_sources = sorted(srcdir.glob('*.z80'))
    spasm = find_spasm() if asm_sources else None
    if asm_sources and not spasm:
        print('skipped %s: spasm-ng not found (tools/spasm/spasm64.exe or on PATH)'
              % ', '.join(p.name for p in asm_sources))
    for src in asm_sources if spasm else ():
        stem = src.stem
        name = stem.replace('_theta_', 'θ')
        path = outdir / (stem + '.8xp')
        path.unlink(missing_ok=True)       # so a failed assembly can't leave an old one to test
        data, labels = assemble(src, spasm)
        (outdir / (stem + '.lab')).write_text(labels, encoding='ascii')
        prog = TIProtectedAsmProgram(name=name)
        prog.data = data
        prog.save(str(path))
        finish_8xp(path, ASM_COMMENTS.get(name, 'Assembly program - run with Asm('))
        assert bytes(TIProtectedAsmProgram.open(str(path)).data) == data
        print('%-32s %5d bytes' % (shown + stem + '.8xp', len(data)))

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
        check_letters(src.name, text, bytes(prog.data))
        # a TI-84+ command (startTmr) is allowed with a warning; a color calculator's token
        # (max munch turned "Redraw" into the CE color Red) fails the build
        model = prog.get_min_os().model
        if model in TI84P:
            print('warning: %s needs a TI-84+ (startTmr or another TI-84+ command), so it won\'t '
                  'run on a TI-83+' % src.name)
        elif model not in TI83P:
            raise SystemExit('%s needs a %s token; if max munch picked it, escape it with \\ '
                             '(like R\\edraw)' % (src.name, model))
        save_program(name, bytes(prog.data), outdir / (stem + '.8xp'), BASIC_COMMENTS.get(name, 'TI-BASIC program'))
        print('%-32s %5d token bytes' % (shown + stem + '.8xp', len(prog.data)))


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
    print('%-32s %5d entries' % ('build/' + name + '.8xl', len(values)))


def decompile(path, out=None):
    prog = TIProgram.open(str(path))
    data = bytes(prog.data)
    if data[:2] == b'\xbb\x6d':      # a compiled assembly program: no text to show
        text = 'assembly program, %d bytes:\n%s' % (len(data), data.hex(' '))
    elif data[:1] == b'\x3a':        # Axe sources start with a "." header line
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
