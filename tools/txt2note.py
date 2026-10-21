"""Convert a text file to a NoteFolio note (an .8xv appvar) to send to the calculator.

  python tools/txt2note.py notes.txt                  NOTES.8xv next to notes.txt, note NOTES
  python tools/txt2note.py notes.txt -n TODO          note TODO (A-Z and 0-9, 1-8 characters,
                                                      starting with a letter)
  python tools/txt2note.py notes.txt -o out/X.8xv     choose the output file
  python tools/txt2note.py notes.txt --ram            send it to RAM (default: the archive, where
                                                      NoteFolio keeps its notes)
  python tools/txt2note.py notes.txt --replace '?'    put ? for characters the calculator lacks
                                                      (without it they are listed and nothing is
                                                      written)

The text is read as UTF-8 (a BOM is allowed). Line breaks (LF, CRLF or CR) become the
calculator's Enter, a tab becomes a space, and one line break at the very end is dropped.
Curly quotes, dashes and a few other typographic characters become their plain ASCII
look-alikes (counted in the summary). Letters and symbols in the calculator's character set
(accented letters, Greek, superscripts, subscripts, some math) get their own codes; see
CHARS below.

Layout (docs/design.md, "Notefolio format", checked against tests/data/TEST.8xv): F3 47 BF AF,
4 bytes copied from TEST.8xv, the title (the name, 0-padded to 8), the words textlen+24, 18h,
textlen+24, 1, the text, 00h, then 2 bytes whose meaning isn't known (written as 00 00, as
CodeChat's CCOUT note does).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SIG = bytes([0xF3, 0x47, 0xBF, 0xAF])
UNKNOWN = bytes([0x80, 0x10, 0x62, 0x21])        # bytes 4-7 of TEST.8xv's data
MAX_TEXT = 65535 - 2 - 27                        # an appvar's data (size word + note) ≤ 65535

# The calculator's character codes (ti83plus.inc, the L... equates) for characters that aren't
# ASCII, or that the calculator stores somewhere else than ASCII does
CHARS = {
    '\n': 0xD6, '$': 0xF2, '[': 0xC1, 'θ': 0x5B, '⁴': 0x24,
    '√': 0x10, '²': 0x12, '∠': 0x13, '°': 0x14, 'ʳ': 0x15, 'ᵀ': 0x16, '≤': 0x17, '≠': 0x18,
    '≥': 0x19, '⁻': 0x1A, 'ᴇ': 0x1B, '→': 0x1C, '↑': 0x1E, '↓': 0x1F, '³': 0xD5,
    '¿': 0xB9, '¡': 0xBA, '…': 0xCE, '𝑖': 0xD7, 'χ': 0xD9,
    'α': 0xBB, 'β': 0xBC, 'γ': 0xBD, 'Δ': 0xBE, 'δ': 0xBF, 'ε': 0xC0, 'λ': 0xC2, 'μ': 0xC3,
    'π': 0xC4, 'ρ': 0xC5, 'Σ': 0xC6, 'σ': 0xC7, 'τ': 0xC8, 'φ': 0xC9, 'Ω': 0xCA,
}
CHARS.update({chr(0x2080 + k): 0x80 + k for k in range(10)})            # ₀-₉
CHARS.update({c: 0x8A + k for k, c in enumerate('ÁÀÂÄáàâäÉÈÊËéèêëÍÌÎÏíìîïÓÒÔÖóòôöÚÙÛÜúùûüÇçÑñ')})
# Typographic characters with a plain look-alike
LOOKALIKE = {'‘': "'", '’': "'", '‚': "'", '′': "'", '“': '"', '”': '"', '„': '"', '″': '"',
             '–': '-', '—': '-', '‐': '-', '−': '-', ' ': ' ', '\t': ' '}


def to_calc(text, replace=None):
    """Text → calculator character codes. Returns (bytes, look-alikes used, problems), where
    problems lists (line, column, character) for each character without a code (replaced by
    `replace` if given)."""
    out, swapped, bad = bytearray(), 0, []
    line, col = 1, 0
    for c in text:
        col += 1
        if c in LOOKALIKE:
            c = LOOKALIKE[c]
            swapped += 1
        if c in CHARS:
            out.append(CHARS[c])
        elif ' ' <= c <= '~':
            out.append(ord(c))
        else:
            bad.append((line, col, c))
            if replace is not None:
                out.append(ord(replace))
        if c == '\n':
            line, col = line + 1, 0
    return bytes(out), swapped, bad


def note(name, text_bytes):
    """The appvar's data (without the size word tivars adds) for a note holding text_bytes."""
    n = len(text_bytes) + 24
    return (SIG + UNKNOWN + name.encode('ascii').ljust(8, b'\0') +
            n.to_bytes(2, 'little') + (24).to_bytes(2, 'little') + n.to_bytes(2, 'little') +
            (1).to_bytes(2, 'little') + text_bytes + b'\0' + b'\0\0')


def note_name(stem):
    """A default note name from a file name: its letters and digits, uppercase, at most 8."""
    name = ''.join(c for c in stem.upper() if c.isascii() and c.isalnum())[:8]
    return name if name[:1].isalpha() else ('N' + name)[:8]


def check_name(name):
    if not (1 <= len(name) <= 8 and name.isascii() and name.isalnum() and name.isupper()
            and name[0].isalpha()):
        raise SystemExit('note names are 1-8 characters, A-Z and 0-9, starting with a letter: %r'
                         % name)


def save(path, name, data, archived=True):
    from tivars import TIAppVar
    import build
    var = TIAppVar(name=name)
    var.data = data                  # tivars adds the size word
    var.archived = archived          # tivars' default is archived, like TI Connect's files
    path.parent.mkdir(parents=True, exist_ok=True)
    var.save(str(path))
    build.finish_8xp(path, 'NoteFolio note %s' % name)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Convert a text file to a NoteFolio note (.8xv).')
    ap.add_argument('input', type=Path, help='the text file (UTF-8)')
    ap.add_argument('-n', '--name', help='note name (default: from the file name)')
    ap.add_argument('-o', '--output', type=Path, help='output file (default: NAME.8xv next to the input)')
    ap.add_argument('--ram', action='store_true', help='send it to RAM instead of the archive')
    ap.add_argument('--replace', metavar='CHAR',
                    help='an ASCII character to put in place of characters the calculator lacks')
    args = ap.parse_args(argv)

    name = args.name.upper() if args.name is not None else note_name(args.input.stem)
    check_name(name)
    if args.replace is not None and not (len(args.replace) == 1 and ' ' <= args.replace <= '~'):
        raise SystemExit('--replace takes one printable ASCII character')
    try:
        text = args.input.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError as e:
        raise SystemExit('%s is not UTF-8 text (%s)' % (args.input, e))
    except OSError as e:
        raise SystemExit('can\'t read %s: %s' % (args.input, e.strerror))
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if text.endswith('\n'):
        text = text[:-1]

    data, swapped, bad = to_calc(text, args.replace)
    if bad and args.replace is None:
        shown = ', '.join('line %d col %d %r (U+%04X)' % (l, c, ch, ord(ch)) for l, c, ch in bad[:10])
        more = ' and %d more' % (len(bad) - 10) if len(bad) > 10 else ''
        raise SystemExit('%d character(s) the calculator lacks: %s%s\n'
                         'Use --replace "?" to write them as ?.' % (len(bad), shown, more))
    if len(data) > MAX_TEXT:
        raise SystemExit('too long: %d characters, a note holds at most %d' % (len(data), MAX_TEXT))

    out = args.output or args.input.with_name(name + '.8xv')
    save(out, name, note(name, data), not args.ram)
    print('%s: note %s, %d characters, appvar size %d, %s' % (out, name, len(data), len(data) + 27,
                                                            'RAM' if args.ram else 'archived'))
    if swapped:
        print('  %d typographic character(s) (curly quotes, dashes, tabs, ...) written as ASCII' % swapped)
    if bad:
        print('  %d character(s) the calculator lacks written as %r' % (len(bad), args.replace))


if __name__ == '__main__':
    main()
