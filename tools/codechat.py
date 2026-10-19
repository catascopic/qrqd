"""CodeChat on the PC: keyrings for the calculator, and the reference encrypt/decrypt.

  python tools/codechat.py loopkey                  build/CCKEYS.8xv: one key, two entries,
                                                    LOOP0 (side 0) and LOOP1 (side 1), so one
                                                    calculator can send to itself
  python tools/codechat.py newkey ALICE BOB         build/keys/ALICE.8xv (holds contact BOB, side 0)
                                                    and build/keys/BOB.8xv (contact ALICE, side 1);
                                                    both are appvar CCKEYS, send one to each person
  python tools/codechat.py encrypt KEYS.8xv NAME COUNTER TEXT   digits for a message to NAME
  python tools/codechat.py decrypt KEYS.8xv DIGITS  who sent it, and the text

Message: header (6 bytes: version/flags, key ID, counter big-endian) + AES-SIV tag (16) +
ciphertext, with the header as AES-SIV's associated data (RFC 5297). Version 1 in the high
nibble of byte 0; bit 0 = compact alphabet, bit 1 = odd character count. The counter's last
bit is the sender's side. Key ID = first byte of AES-128 under the key's second half (the CTR
key) of a zero block. Bytes become digits two at a time (00000-65535), a last odd byte three.
Compact alphabet: 0-9, A-Z, then space ? ! ' , - . / : (values 0-44), two characters in 11
bits (45a+b), an odd last one in 6, padded with zero bits.
Plaintext in 8-bit mode is calculator character codes: ASCII, except $ = F2h, [ = C1h.

Keyring appvar CCKEYS: version 1, entry count, then per entry: name (8 bytes, 0-padded),
my side (0/1), key (32 bytes).
"""
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.exceptions import InvalidTag

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ' + " ?!',-./:"
VERSION = 1
HEADER = 6
TAG = 16
ENTRY = 41                     # name 8, side 1, key 32
TO_CALC = {'$': 0xF2, '[': 0xC1}
FROM_CALC = {v: k for k, v in TO_CALC.items()}


# ---------- text ----------
def compact_ok(text):
    return all(c in ALPHABET for c in text)


def pack(text):
    """Compact alphabet: pairs in 11 bits, an odd last character in 6, zero-padded."""
    bits = ''
    for k in range(0, len(text) - 1, 2):
        bits += format(45 * ALPHABET.index(text[k]) + ALPHABET.index(text[k + 1]), '011b')
    if len(text) % 2:
        bits += format(ALPHABET.index(text[-1]), '06b')
    bits += '0' * (-len(bits) % 8)
    return bytes(int(bits[k:k + 8], 2) for k in range(0, len(bits), 8))


def unpack(data, odd):
    bits = ''.join(format(b, '08b') for b in data)
    pairs = (len(bits) - 6) // 11 if odd else len(bits) // 11
    out = ''
    for k in range(pairs):
        v = int(bits[11 * k:11 * k + 11], 2)
        out += ALPHABET[v // 45] + ALPHABET[v % 45]
    if odd:
        out += ALPHABET[int(bits[11 * pairs:11 * pairs + 6], 2)]
    return out


def to_calc(text):
    return bytes(TO_CALC.get(c, ord(c)) for c in text)


def from_calc(data):
    return ''.join(FROM_CALC.get(b, chr(b)) for b in data)


# ---------- digits ----------
def to_digits(data):
    out = ''.join('%05d' % (data[k] << 8 | data[k + 1]) for k in range(0, len(data) - 1, 2))
    return out + ('%03d' % data[-1] if len(data) % 2 else '')


def from_digits(text):
    d = ''.join(c for c in text if c.isdigit())
    if len(d) % 5 not in (0, 3):
        raise ValueError('wrong number of digits (%d)' % len(d))
    out = bytearray()
    for k in range(0, len(d) - len(d) % 5, 5):
        v = int(d[k:k + 5])
        if v > 65535:
            raise ValueError('group %d is over 65535' % (k // 5 + 1))
        out += bytes([v >> 8, v & 255])
    if len(d) % 5:
        v = int(d[-3:])
        if v > 255:
            raise ValueError('last group is over 255')
        out.append(v)
    return bytes(out)


def digit_count(nbytes):
    return 5 * (nbytes // 2) + 3 * (nbytes % 2)


# ---------- crypto ----------
def key_id(key):
    enc = Cipher(algorithms.AES(key[16:]), modes.ECB()).encryptor()
    return (enc.update(bytes(16)) + enc.finalize())[0]


def encrypt(key, counter, text, compact=None):
    """Message bytes for TEXT. compact=None picks compact when every character allows it."""
    if compact is None:
        compact = compact_ok(text)
    if compact:
        plain, flags = pack(text), 1 | (len(text) % 2) << 1
    else:
        plain, flags = to_calc(text), 0
    header = bytes([VERSION << 4 | flags, key_id(key)]) + counter.to_bytes(4, 'big')
    return header + AESSIV(key).encrypt(plain, [header])


def decrypt(message, entries):
    """(contact name, text) using the first keyring entry that opens it, or raise ValueError."""
    if len(message) < HEADER + TAG:
        raise ValueError('too short')
    header, body = message[:HEADER], message[HEADER:]
    if header[0] >> 4 != VERSION:
        raise ValueError('unknown format %d' % (header[0] >> 4))
    side = header[5] & 1
    own = tried = False
    for name, my_side, key in entries:
        if key_id(key) != header[1]:
            continue
        if my_side == side:
            own = True
            continue
        tried = True
        try:
            plain = AESSIV(key).decrypt(body, [header])
        except InvalidTag:
            continue
        if header[0] & 1:
            return name, unpack(plain, header[0] >> 1 & 1)
        return name, from_calc(plain)
    raise ValueError('your own message' if own and not tried else 'no key opens it (wrong key or a typo)')


# ---------- keyring appvar ----------
def keyring(entries):
    data = bytes([VERSION, len(entries)])
    for name, side, key in entries:
        data += name.encode('ascii').ljust(8, b'\0')[:8] + bytes([side]) + key
    return data


def read_keyring(data):
    n = data[1]
    out = []
    for k in range(n):
        e = data[2 + ENTRY * k:2 + ENTRY * (k + 1)]
        out.append((e[:8].rstrip(b'\0').decode('ascii'), e[8], bytes(e[9:41])))
    return out


def save_appvar(path, name, data, comment):
    from tivars import TIAppVar
    import build
    var = TIAppVar(name=name)
    var.data = data                  # tivars adds the size word
    path.parent.mkdir(parents=True, exist_ok=True)
    var.save(str(path))
    build.finish_8xp(path, comment)


def load_appvar(path):
    from tivars import TIAppVar
    return bytes(TIAppVar.open(str(path)).data)


def check_name(name):
    if not (1 <= len(name) <= 8 and name.isascii() and name.isalnum() and name.upper() == name):
        raise SystemExit('names are 1-8 characters, A-Z and 0-9: %r' % name)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'loopkey':
        key = os.urandom(32)
        path = ROOT / 'build' / 'CCKEYS.8xv'
        save_appvar(path, 'CCKEYS', keyring([('LOOP0', 0, key), ('LOOP1', 1, key)]), 'CodeChat test keyring')
        print('%s: LOOP0 and LOOP1, key ID %02X' % (path.relative_to(ROOT), key_id(key)))
    elif cmd == 'newkey' and len(sys.argv) == 4:
        a, b = sys.argv[2], sys.argv[3]
        check_name(a); check_name(b)
        key = os.urandom(32)
        for me, other, side in ((a, b, 0), (b, a, 1)):
            path = ROOT / 'build' / 'keys' / (me + '.8xv')
            save_appvar(path, 'CCKEYS', keyring([(other, side, key)]), 'CodeChat keyring of ' + me)
            print('%s: contact %s, side %d' % (path.relative_to(ROOT), other, side))
        print('key ID %02X' % key_id(key))
    elif cmd == 'encrypt' and len(sys.argv) == 6:
        entries = read_keyring(load_appvar(sys.argv[2]))
        name, my_side, key = next(e for e in entries if e[0] == sys.argv[3])
        counter = int(sys.argv[4])
        if counter % 2 != my_side:
            raise SystemExit('side %d sends %s counters' % (my_side, 'odd' if my_side else 'even'))
        print(to_digits(encrypt(key, counter, sys.argv[5])))
    elif cmd == 'decrypt' and len(sys.argv) >= 4:
        entries = read_keyring(load_appvar(sys.argv[2]))
        name, text = decrypt(from_digits(' '.join(sys.argv[3:])), entries)
        print('from %s: %s' % (name, text))
    else:
        print(__doc__)
