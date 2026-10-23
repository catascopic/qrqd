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

# The engine under test is SRC, run by Engine(SRC):
# - the release's engine, the Z80 one (src/_theta_QR.z80, docs/asm_port.md): the build's
#   .8xp in tools/z80sim.py (Engine = AsmMachine), with the interface of docs/API.md
# - for a test_legacy_*.py script: the older set's Axe engine (src/legacy/QRSRC.axe.txt), with
#   its own interface (docs/legacy/API.md), in tools/axesim.py
# Machine stays axesim's, for the Axe tools' tests (LOREM, UNPROT, CodeChat). The frozen Axe
# engine (src/legacy/QRAXE.axe.txt) keeps the interface before design.md item 53 and isn't
# tested any more.
LEGACY = Path(sys.argv[0]).name.startswith('test_legacy')
ASM = not LEGACY
if ASM:
    from z80sim import AsmMachine as Engine, Z80Error  # noqa: E402,F401
    SRC = ROOT / 'build' / '_theta_QR.8xp'
    if not SRC.exists():
        sys.exit('%s is missing: run tools/build.py (it needs spasm-ng in tools/spasm/)'
                 % SRC.relative_to(ROOT))
else:
    Engine = Machine
    SRC = (ROOT / 'src' / 'legacy' / 'QRSRC.axe.txt').read_text(encoding='utf-8')
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


# The engine's interface (docs/API.md); the legacy tests define the old one themselves
CHECK, DRAW, LIST = 0, 1, 2                  # C: the command
STR1, NOTE = 0, 1                            # I: the input
AUTO, ASCII, ALNUM = 0, 1, 2                 # M: the mode (auto only for a check)
BAD = 65533                                  # Ans for a character that can't be encoded (position in B)


def bad(k):
    """(Ans, B) of a call that fails at character k."""
    return (BAD, k)


def run_engine(source, version, count, mode, str1=None, skip=0):
    """Run the engine on Str1 the way prgmQR does: version 0 = a check (C=0), else a draw
    (C=1) of `count` characters after `skip`. A draw in auto mode is a check first, then
    the draw with M from the check's Ans (odd: 2 alphanumeric, else 1 ASCII); a check that
    fails is returned instead, as prgmQR would stop there."""
    if version and mode == AUTO:
        c = run_engine(source, 0, 0, mode, str1=str1)
        if c.ans >= 65532:
            return c
        mode = 1 + (c.ans & 1)
    m = Engine(SRC)
    for name, v in zip('CIVNMOB', (DRAW if version else CHECK, source, version, count, mode, skip, 0)):
        m.set_real(name, v)
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


def data_codewords(payload, version, mode):
    """The data codewords (before error correction) at EC level L: mode indicator, count,
    data, up to 4 terminator bits, zero bits to a byte boundary, pad bytes ECh 11h in turn.
    Built from the qrcode library's own pieces, as its util.create_data does before adding EC,
    so it doesn't share any code with the engines."""
    from qrcode.base import rs_blocks
    from qrcode.util import BitBuffer, length_in_bits, PAD0, PAD1
    data = QRData(payload.encode() if isinstance(payload, str) else bytes(payload),
                  mode=MODE_ALPHA_NUM if mode == 'alphanumeric' else MODE_8BIT_BYTE)
    buf = BitBuffer()
    buf.put(data.mode, 4)
    buf.put(len(data), length_in_bits(data.mode, version))
    data.write(buf)
    limit = sum(b.data_count * 8 for b in rs_blocks(version, qrcode.constants.ERROR_CORRECT_L))
    assert len(buf) <= limit, 'payload too long for the version'
    for _ in range(min(limit - len(buf), 4)):
        buf.put_bit(False)
    while len(buf) % 8:
        buf.put_bit(False)
    for i in range((limit - len(buf)) // 8):
        buf.put(PAD1 if i % 2 else PAD0, 8)
    return bytes(buf.buffer)


def ec_codewords(payload, version, mode):
    """The EC codewords in the engines' layout: block after block, R each. Taken from the
    qrcode library's full codeword sequence (util.create_data: data, then EC interleaved,
    EC byte i of every block in turn), so EC byte i of block b is at M + i·blocks + b."""
    from qrcode.base import rs_blocks
    from qrcode.util import create_data
    data = QRData(payload.encode() if isinstance(payload, str) else bytes(payload),
                  mode=MODE_ALPHA_NUM if mode == 'alphanumeric' else MODE_8BIT_BYTE)
    blocks = rs_blocks(version, qrcode.constants.ERROR_CORRECT_L)
    allcw = create_data(version, qrcode.constants.ERROR_CORRECT_L, [data])
    M = sum(b.data_count for b in blocks)
    R = blocks[0].total_count - blocks[0].data_count
    return bytes(allcw[M + i * len(blocks) + b] for b in range(len(blocks)) for i in range(R))


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
