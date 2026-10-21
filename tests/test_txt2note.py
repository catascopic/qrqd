"""Tests for tools/txt2note.py, the text file → NoteFolio note converter.

The note it writes must have the layout of a real one (tests/data/TEST.8xv), and the QR
engine must read it back as the text that went in.

  python tests/test_txt2note.py
"""
import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from qrtest import ROOT, decode, matrix_from, AUTO, NOTE
from test_notefolio import machine, expect, failures

sys.path.insert(0, str(ROOT / 'tools'))
import txt2note                                                  # noqa: E402
from tivars import TIAppVar                                      # noqa: E402


def convert(text, *args, raw=None):
    """Run the command line on a file holding text (or the bytes raw); returns (note name,
    archived, data) of the .8xv it wrote, or the SystemExit message."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / 'my notes.txt'
        src.write_bytes(raw if raw is not None else text.encode('utf-8'))
        try:
            with redirect_stdout(io.StringIO()):
                txt2note.main([str(src), *args])
        except SystemExit as e:
            return str(e)
        out = list(Path(tmp).glob('*.8xv'))
        assert len(out) == 1, out
        v = TIAppVar.open(str(out[0]))
        return out[0].name, v.name, v.archived, bytes(v.data)


def text_of(data):
    """The text bytes of a note's data (from byte 24 up to the 00h end)."""
    return data[24:data.index(0, 24)]


def layout():
    real = TIAppVar.open(str(ROOT / 'tests' / 'data' / 'TEST.8xv'))
    rd = bytes(real.data)
    mine = txt2note.note('TEST', text_of(rd))
    # the same apart from the title's junk after its 0 (TEST\0LED) and the 2 unknown last bytes
    expect('layout matches TEST.8xv (signature, 4 bytes, header words, text, 00h)',
           len(mine) == len(rd) and mine[:12] == rd[:12] and mine[16:-2] == rd[16:-2],
           (mine.hex(' '), rd.hex(' ')))
    expect('title: the name, 0-padded to 8', mine[8:16] == b'TEST\0\0\0\0')


def characters():
    data, swapped, bad = txt2note.to_calc('a[b]$\nθ⁴ é Ñ π ₂ ≤ →')
    expect('ASCII as is; [ $ Enter θ ⁴ swapped; accents, Greek, subscripts, math',
           data == b'a\xc1b]\xf2\xd6\x5b\x24 \x96 \xb4 \xc4 \x82 \x17 \x1c' and not bad and not swapped,
           data.hex(' '))
    data, swapped, bad = txt2note.to_calc('it’s “so” – ok\tyes')
    expect('curly quotes, dashes, tab → ASCII, counted', data == b'it\'s "so" - ok yes' and swapped == 5,
           (data, swapped))
    data, swapped, bad = txt2note.to_calc('ab\n€x🙂', replace='?')
    expect('characters it lacks: positions, then replaced', data == b'ab\xd6?x?' and
           bad == [(2, 1, '€'), (2, 3, '🙂')], (data, bad))


def command_line():
    r = convert('HELLO\n')
    expect('default name from the file name (letters and digits, uppercase), archived',
           r[:3] == ('MYNOTES.8xv', 'MYNOTES', True), r[:3])
    expect('one line break at the end is dropped', text_of(r[3]) == b'HELLO', r[3])
    r = convert('x', '-n', 'todo2', '--ram')
    expect('-n (uppercased) and --ram', r[:3] == ('TODO2.8xv', 'TODO2', False), r[:3])
    r = convert('', raw=b'\xef\xbb\xbfone\r\ntwo\rthree\n\n')
    expect('BOM skipped; CRLF, CR, LF all Enter; only the last break dropped',
           text_of(r[3]) == b'one\xd6two\xd6three\xd6', text_of(r[3]))
    r = convert('price: 5€')
    expect('a character it lacks: refused with its position', isinstance(r, str) and
           'line 1 col 9' in r and '€' in r and '--replace' in r, r)
    r = convert('price: 5€', '--replace', '?')
    expect('--replace ?', text_of(r[3]) == b'price: 5?', r)
    for bad in ('9LIVES', 'TOOLONGNAME', 'A-B', ''):
        r = convert('x', '-n', bad)
        expect('bad name %r refused' % bad, isinstance(r, str) and 'note names' in r, r)
    r = convert('', raw=b'\xff\xfe')
    expect('not UTF-8: refused', isinstance(r, str) and 'not UTF-8' in r, r)


def engine_reads_it():
    """The engine (E=2) encodes the note's text back to the original ASCII ([ $ and newlines
    included); an accented letter only warns, in byte mode."""
    text = 'Shopping [week 3]:\n- milk $2\n- eggs\nTOTAL: 5'
    _, name, _, data = convert(text, '-n', 'SHOP', '--ram')
    m = machine([(name, data, False)], {'E': NOTE, 'V': 3, 'N': len(text), 'M': AUTO}, str2=name)
    got = m.ans == 0 and decode(matrix_from(m, 3))[0].bytes
    expect('engine draws the note; it scans as the text file', got == text.encode(), got)
    _, name, _, data = convert('café', '-n', 'CAFE')
    m = machine([(name, data, True)], {'E': NOTE, 'V': 0, 'M': AUTO}, str2=name)
    expect('archived, an é: the check warns at 4 (byte mode)', (m.ans, m.get_real('B')) == (2 * 4, 4),
           (m.ans, m.get_real('B')))


if __name__ == '__main__':
    layout()
    characters()
    command_line()
    engine_reads_it()
    print('\nALL PASSED' if not failures else '\n%d FAILED' % len(failures))
    sys.exit(1 if failures else 0)
