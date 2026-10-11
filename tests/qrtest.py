"""Shared helpers for the engine tests.

The Axe engine source is run in tools/axesim.py (an interpreter for the subset
of Axe it uses). Each QR code it draws is compared module-for-module with the
`qrcode` library (EC level L, mask 0, forced version and mode) and decoded with
zxing-cpp. Note: segno is NOT a valid reference; it pads short byte-mode data
with an extra 0x00 codeword (harmless, but nonstandard).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

import qrcode                                   # noqa: E402
import zxingcpp                                 # noqa: E402
from PIL import Image                           # noqa: E402
from qrcode.util import QRData, MODE_ALPHA_NUM, MODE_8BIT_BYTE  # noqa: E402
from axesim import Machine, AxeError            # noqa: E402,F401

SRC_DIR = ROOT / 'standalone' / 'src' if '--standalone' in sys.argv else ROOT / 'src'
SRC = (SRC_DIR / 'QRSRC.axe.txt').read_text(encoding='utf-8')
TWO_BYTE = {0x5C, 0x5D, 0x5E, 0x60, 0x61, 0x62, 0x63, 0x7E, 0xAA, 0xBB, 0xEF}


def split_tokens(b):
    out, k = [], 0
    while k < len(b):
        n = 2 if b[k] in TWO_BYTE else 1
        out.append(bytes(b[k:k + n])); k += n
    return out


# Calculator tokens for ASCII 32..126, in order (the quote is the real " token, 2Ah).
ASCII_TOK = split_tokens(bytes.fromhex(
    '292d2a' 'bbd2bbd3bbdabbd4' 'ae1011' '8270' '2b713a83' +            # space ! " # $ % & ' ( ) * + , - . /
    '30313233343536373839' + '3ebbd66b6a6cafbbd1' +                      # 0-9 : ; < = > ? @
    '4142434445464748494a4b4c4d4e4f505152535455565758595a' +              # A-Z
    '06bbd707f0bbd9bbd5' +                                               # [ \ ] ^ _ `
    'bbb0bbb1bbb2bbb3bbb4bbb5bbb6bbb7bbb8bbb9bbbabbbcbbbdbbbebbbfbbc0'
    'bbc1bbc2bbc3bbc4bbc5bbc6bbc7bbc8bbc9bbca' +                         # a-z (no BB BB)
    '08bbd809bbcf'))                                                     # { | } ~
assert len(ASCII_TOK) == 95, len(ASCII_TOK)

ALNUM_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:'
ALNUM_TOK = ([bytes([c]) for c in b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'] + [b'\x29'] +
             split_tokens(bytes.fromhex('bbd3bbda8270713a833e')))      # $ % * + - . / :
assert len(ALNUM_TOK) == 45

CAP_BYTE = [17, 32, 53, 78, 106, 134, 154, 192, 230, 271, 321]
CAP_ALNUM = [25, 47, 77, 114, 154, 195, 224, 279, 335, 395, 468]


def ascii_tokens(s):
    return [ASCII_TOK[ord(c) - 32] for c in s]


def alnum_tokens(s):
    return [ALNUM_TOK[ALNUM_CHARS.index(c)] for c in s]


TEXT, BINARY = 1, 2                          # E: Str1 text, list BIN
AUTO, ASCII, ALNUM = 0, 1, 2                 # M
BAD = 32768                                  # Ans = BAD + position of the first bad character


def run_engine(source, version, count, mode, str1=None, lst=None, skip=0, alnum=None):
    """Run the engine the way prgmQR calls it (version 0 = check text only). An auto-mode
    encode gets A (alphanumeric or not) from a check call first, as prgmQR does, unless
    `alnum` is given."""
    if alnum is None:
        alnum = 0
        if version and mode == AUTO and source == TEXT:
            c = run_engine(source, 0, 0, mode, str1=str1)
            alnum = c.ans & 1 if c.ans < BAD else 0
    m = Machine(SRC)
    for name, v in zip('EVNMOA', (source, version, count, mode, skip, alnum)):
        m.set_real(name, v)
    if source == BINARY:
        m.set_list('BIN', lst)
    else:
        m.set_str(1, b''.join(str1))
    m.run()
    return m


def matrix_from(m, version):
    """Read the symbol back out of the graph buffer; fail on any stray pixel."""
    S = 17 + 4 * version
    G, H = 31 - S // 2, 47 - S // 2      # always centered
    buf = m.displays[-1]
    mat = [[1 if buf[(G + y) * 12 + (H + x) // 8] & (0x80 >> ((H + x) % 8)) else 0
            for x in range(S)] for y in range(S)]
    assert sum(bin(b).count('1') for b in buf) == sum(map(sum, mat)), 'stray pixels'
    return mat


def decode(mat):
    S, sc, q = len(mat), 4, 4
    img = Image.new('L', ((S + 2 * q) * sc,) * 2, 255)
    px = img.load()
    for y in range(S):
        for x in range(S):
            if mat[y][x]:
                for dy in range(sc):
                    for dx in range(sc):
                        px[(x + q) * sc + dx, (y + q) * sc + dy] = 0
    return zxingcpp.read_barcodes(img)


def reference(payload, version, mode):
    q = qrcode.QRCode(version=version, error_correction=qrcode.constants.ERROR_CORRECT_L,
                      mask_pattern=0, border=0)
    data = payload.encode() if isinstance(payload, str) else bytes(payload)
    q.add_data(QRData(data, mode=MODE_ALPHA_NUM if mode == 'alphanumeric' else MODE_8BIT_BYTE))
    q.make(fit=False)
    return [[int(c) for c in r] for r in q.get_matrix()]


def check_symbol(m, version, payload, mode):
    """Engine output must equal the reference symbol and decode to the payload."""
    assert m.ans == 0, 'engine returned %r' % m.ans
    mat = matrix_from(m, version)
    assert mat == reference(payload, version, mode), 'differs from reference encoder'
    if len(payload):                       # decoders don't report empty content
        got = decode(mat)
        want = payload.encode() if isinstance(payload, str) else bytes(payload)
        assert got and got[0].bytes == want, 'decoded %r' % (got[0].bytes if got else None)
    return mat
