"""CodeChat prototype (src/CHATSRC.axe.txt) in the simulator, against tools/codechat.py.

  python tests/test_codechat.py

The program runs as a Flash app would (writes into its own data refused). AES and CMAC
are checked with FIPS-197 and RFC 4493 vectors by calling the subroutines; whole sends are
compared byte for byte with the Python reference (cryptography's AES-SIV), and receives
decrypt messages the reference made.
"""
import os
import sys

from qrtest import ROOT, Machine, ascii_tokens
from axesim import L1

sys.path.insert(0, str(ROOT / 'tools'))
import codechat as cc                                          # noqa: E402

SRC = (ROOT / 'src' / 'CHATSRC.axe.txt').read_text(encoding='utf-8')
CODE = '\n'.join(s for s in SRC.split('\n') if not s.startswith('.'))   # without the comments
K1, K2, K3, K4, CLEAR, ENTER = 0x8F, 0x90, 0x91, 0x92, 9, 5  # the OS _GetKey codes (getKeyʳ)
F1, F2, F3, F4 = 0x49, 0x48, 0x2E, 0x5A                     # Y= WINDOW ZOOM TRACE
SEND, RECEIVE, NEWKEY, QUIT = K1, K2, K3, K4
failures = []
KEY = bytes(range(0x40, 0x60))                                 # a fixed test key
LOOP = [('LOOP0', 0, KEY), ('LOOP1', 1, KEY)]


def expect(name, cond, detail=''):
    print(('ok    ' if cond else 'FAIL  ') + name + ('' if cond else '  ' + str(detail)))
    if not cond:
        failures.append(name)


def tokens(text):
    return b''.join(ascii_tokens(text))


def machine(keys, inputs=(), entries=LOOP, state=None, state_archived=True, keyring_archived=True,
            note=None):
    m = Machine(SRC, app=True)
    if entries is not None:
        m.add_appvar('CCKEYS', cc.keyring(entries), archived=keyring_archived)
    if state is not None:
        m.add_appvar('CCSTATE', state.to_bytes(4, 'big'), archived=state_archived)
    if note is not None:
        m.add_appvar('CCOUT', note)
    m.keys = list(keys)
    m.inputs = [tokens(t) if isinstance(t, str) else t for t in inputs]
    m.run()
    return m


def sent(m):
    """(digits in note CCOUT, counter in CCSTATE, CCSTATE archived?)"""
    note, _ = m.appvar('CCOUT')
    g = int.from_bytes(note[16:18], 'little') - 24
    assert note[:4] == bytes.fromhex('F347BFAF') and note[24 + g:] == bytes(3) and len(note) == g + 27, note[:30]
    state, archived = m.appvar('CCSTATE')
    return note[24:24 + g].decode(), int.from_bytes(state, 'big'), archived


def shown(m):
    return '\n'.join('\n'.join(s) for s in m.screens)


def unit():
    # FIPS-197 appendix C.1
    m = Machine(SRC, app=True)
    m.mem[L1 + 339:L1 + 355] = bytes(range(16))
    m.call('KX', L1 + 339)
    m.mem[L1 + 640:L1 + 656] = bytes.fromhex('00112233445566778899aabbccddeeff')
    m.call('AE', L1 + 640)
    got = bytes(m.mem[L1 + 640:L1 + 656]).hex()
    expect('AES-128 FIPS-197 C.1', got == '69c4e0d86a7b0430d8cdb78070b4c55a', got)
    # RFC 4493 section 4
    key = bytes.fromhex('2b7e151628aed2a6abf7158809cf4f3c')
    msg = bytes.fromhex('6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e51'
                        '30c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710')
    want = {0: 'bb1d6929e95937287fa37d129b756746', 16: '070a16b46b4d4144f79bdd9dd04a287c',
            40: 'dfa66747de9ae63030ca32611497c827', 64: '51f0bebf7e3b9d92fc49741779363cfe'}
    for n, mac in want.items():
        m = Machine(SRC, app=True)
        m.mem[L1 + 339:L1 + 355] = key
        m.call('KX', L1 + 339)
        m.call('SK')
        m.mem[L1 + 22:L1 + 22 + n] = msg[:n]
        m.call('CM', L1 + 22, n)
        got = bytes(m.mem[L1 + 624:L1 + 640]).hex()
        expect('AES-CMAC RFC 4493, %d bytes' % n, got == mac, got)


def sending():
    # one contact (no menu): BOB's keyring holds ALICE, side 1; a compact message
    bob = [('ALICE', 1, KEY)]
    m = machine([SEND, ENTER, QUIT], ['HELLO WORLD'], entries=bob)
    digits, counter, archived = sent(m)
    want = cc.to_digits(cc.encrypt(KEY, 1, 'HELLO WORLD'))
    expect('compact send matches the reference byte for byte (%d digits)' % len(digits), digits == want,
           (digits, want))
    expect('first counter on side 1 is 1, saved and archived', (counter, archived) == (1, True), (counter, archived))
    expect('ALICE (side 0) reads it', cc.decrypt(cc.from_digits(digits), [('BOB', 0, KEY)]) == ('BOB', 'HELLO WORLD'))
    expect('the screen says where it went', 'SENT TO ALICE' in shown(m) and 'IN NOTE CCOUT' in shown(m), shown(m))

    m = machine([SEND, ENTER, QUIT], ['NEXT'], entries=bob, state=1)
    digits, counter, _ = sent(m)
    expect('the counter goes up by 2, keeping the side (1 -> 3)',
           counter == 3 and digits == cc.to_digits(cc.encrypt(KEY, 3, 'NEXT')), counter)
    m = machine([SEND, ENTER, QUIT], ['X'], entries=[('BOB', 0, KEY)], state=3, state_archived=False)
    expect('side 0 after counter 3 sends 4', sent(m)[1:] == (4, True), sent(m)[1:])

    # two contacts: a menu; pick the second
    m = machine([SEND, K2, ENTER, QUIT], ["IT'S 5:30/OK?!"], entries=LOOP)
    digits, counter, _ = sent(m)
    expect('contact menu: 2 picks LOOP1 (side 1), punctuation stays compact',
           counter == 1 and digits == cc.to_digits(cc.encrypt(KEY, 1, "IT'S 5:30/OK?!")), counter)
    expect('the menu lists both names', '1 LOOP0' in shown(m) and '2 LOOP1' in shown(m), shown(m))

    for keys, want_text, what in (([K1], 'HELLO THERE', 'uppercase'), ([K2], 'Hello there', 'as typed')):
        m = machine([SEND, K1] + keys + [ENTER, QUIT], ['Hello there'])
        digits, counter, _ = sent(m)
        expect('lowercase, %s' % what,
               digits == cc.to_digits(cc.encrypt(KEY, 2, want_text, compact=what == 'uppercase')), digits)
    expect('the lowercase question shows both digit counts',
           '1 UPPERCASE   ' + str(cc.digit_count(22 + len(cc.pack('HELLO THERE')))) in shown(m)
           and '2 AS TYPED    ' + str(cc.digit_count(22 + 11)) in shown(m), shown(m))

    m = machine([SEND, K1, K1, ENTER, QUIT], ['COST $5 [OK]'])
    digits, _, _ = sent(m)
    expect('$ and [ go 8-bit (as F2h, C1h) after a confirmation',
           cc.decrypt(cc.from_digits(digits), LOOP) == ('LOOP1', 'COST $5 [OK]')
           and digits == cc.to_digits(cc.encrypt(KEY, 2, 'COST $5 [OK]', compact=False)), digits)
    m = machine([SEND, K1, K2, QUIT], ['COST $5'])
    expect('cancelling the 8-bit question sends nothing', 'CCOUT' not in m.appvars and 'CCSTATE' not in m.appvars)

    m = machine([SEND, K1, ENTER, QUIT], ['A'], entries=LOOP)
    expect('one character', cc.decrypt(cc.from_digits(sent(m)[0]), LOOP)[1] == 'A')
    m = machine([SEND, K1, ENTER, QUIT], [b''])
    expect('an empty message', cc.decrypt(cc.from_digits(sent(m)[0]), LOOP)[1] == '')
    m = machine([SEND, K1, ENTER, QUIT], [tokens('AB') + b'\xc2'])            # sin(
    expect('a token with no character is refused', 'BAD CHARACTER' in shown(m) and 'CCOUT' not in m.appvars)
    for n, ok in ((416, True), (417, False)):
        m = machine([SEND, K1, ENTER, QUIT], ['A' * n])
        expect('%d compact characters %s' % (n, 'fit' if ok else 'are too long'),
               ('CCOUT' in m.appvars) == ok and (ok or 'TOO LONG' in shown(m)))
    for n, ok in ((286, True), (287, False)):
        m = machine([SEND, K1, K1, ENTER, QUIT], ['$' * n])
        expect('%d 8-bit characters %s' % (n, 'fit' if ok else 'are too long'), ('CCOUT' in m.appvars) == ok)
    m = machine([SEND, ENTER, QUIT], ['HI'], entries=None)
    expect('no keyring: a message', 'NO KEYRING' in shown(m))
    m = machine([SEND, ENTER, QUIT], ['HI'], entries=[('BOB', 0, KEY)], keyring_archived=False)
    expect('a keyring in RAM works too', cc.decrypt(cc.from_digits(sent(m)[0]), [('X', 1, KEY)])[1] == 'HI')


def receiving():
    def receive(message, entries=LOOP, extra=(), grouped=True):
        d = cc.to_digits(message)
        if grouped:
            d = ' '.join(d[k:k + 5] for k in range(0, len(d), 5))
        return machine([RECEIVE, K1] + list(extra) + [ENTER, QUIT], [d], entries=entries)

    m = receive(cc.encrypt(KEY, 7, 'MEET AT 5'))
    expect('typed digits (in groups) from side 1 open with LOOP0', 'FROM LOOP0' in shown(m)
           and 'MEET AT 5' in shown(m), shown(m))
    m = receive(cc.encrypt(KEY, 8, 'Lower $ [x]'), grouped=False)
    expect('8-bit text shows as calculator characters', 'Lower \xf2 \xc1x]' in shown(m), shown(m))
    m = receive(cc.encrypt(KEY, 8, 'SIDE 0'), entries=[('ALICE', 0, KEY)])
    expect('my own side: "sent by you"', 'SENT BY YOU' in shown(m), shown(m))
    m = receive(cc.encrypt(os.urandom(32), 7, 'OTHER KEY'))
    expect('another key: cannot open', 'CANNOT OPEN IT' in shown(m), shown(m))
    msg = bytearray(cc.encrypt(KEY, 7, 'TAMPERED'))
    msg[-1] ^= 1
    m = receive(bytes(msg))
    expect('one changed byte: cannot open', 'CANNOT OPEN IT' in shown(m), shown(m))
    m = machine([RECEIVE, K1, ENTER, QUIT], ['1234'])
    expect('a wrong digit count is caught', 'BAD DIGIT COUNT' in shown(m), shown(m))
    m = machine([RECEIVE, K1, ENTER, QUIT], ['99999'])
    expect('a group over 65535 is caught', 'BAD DIGITS' in shown(m), shown(m))

    long_text = ' '.join(['WORD%d' % k for k in range(40)])[:200].rstrip()
    m = receive(cc.encrypt(KEY, 9, long_text), extra=[ENTER])
    pages = [s for s in m.screens if s[0].startswith(('FROM', '(CONTINUED)'))]
    text = ''.join(''.join(s[1:]) for s in pages).rstrip()
    expect('a long message pages (112 characters a page)', len(pages) == 2 and text == long_text, pages)

    # round trip on the calculator: send to CCOUT, then read it back
    m = machine([SEND, K1, ENTER, RECEIVE, K2, ENTER, QUIT], ['ROUND TRIP 123'])
    expect('send, then Receive > Read CCOUT', 'FROM LOOP1' in shown(m) and 'ROUND TRIP 123' in shown(m), shown(m))
    m = machine([RECEIVE, K2, ENTER, QUIT], [])
    expect('no CCOUT: a message', 'NO NOTE CCOUT' in shown(m), shown(m))


def qr_engine_reads_ccout():
    """The note CodeChat writes is one prgmθQR opens: all digits, so alphanumeric."""
    from qrtest import SRC as ENGINE
    m = machine([SEND, K1, ENTER, QUIT], ['FOR THE QR CODE'])
    note, _ = m.appvar('CCOUT')
    q = Machine(ENGINE)
    q.add_appvar('CCOUT', note)
    q.build_vat()
    for k, v in {'E': 3, 'V': 0, 'M': 0, 'B': 0}.items():
        q.set_real(k, v)
    q.set_str(2, b'CCOUT')
    q.run()
    digits = sent(m)[0]
    expect('prgmθQR checks note CCOUT as %d alphanumeric characters' % len(digits),
           q.ans == 2 * len(digits) + 1, q.ans)


def menus():
    expect('every key wait is the OS getKey (auto power-down, 2nd+ON)',
           CODE.count('getKey') == CODE.count('getKeyʳ') > 0)
    m = machine([F1, ENTER, F4], ['HI'], entries=[('BOB', 0, KEY)])
    expect('F1 sends and F4 quits, like 1 and 4', 'CCOUT' in m.appvars and m.home == {}, shown(m))
    m = machine([F2, F2, ENTER, F4], [], note=None)
    expect('F2 opens Receive, and F2 picks its second line', 'NO NOTE CCOUT' in shown(m), shown(m))
    m = machine([F3, ENTER, CLEAR], [])
    expect('F3 is New key; Clear quits', 'MAKE KEYS ON PC' in shown(m) and m.home == {}, shown(m))
    m = machine([ENTER, 0x8E, F4], [])
    expect('other keys at the main menu do nothing', len(m.screens) == 3 and 'CCOUT' not in m.appvars)
    m = machine([RECEIVE, CLEAR, QUIT], [])
    expect('Clear backs out of Receive to the main menu', m.screens[-1][0].startswith('CODECHAT'), shown(m))
    m = machine([SEND, CLEAR, QUIT], [])
    expect('Clear backs out of the contact list', m.screens[-1][0].startswith('CODECHAT') and 'CCOUT' not in m.appvars)
    m = machine([SEND, F2, ENTER, QUIT], ['F KEYS'])
    expect('F2 picks the second contact', sent(m)[1] == 1, sent(m))
    m = machine([SEND, K1, F1, ENTER, QUIT], ['Hello'])
    expect('F1 answers "uppercase"', cc.decrypt(cc.from_digits(sent(m)[0]), LOOP)[1] == 'HELLO')
    m = machine([SEND, K1, CLEAR, QUIT], ['Hello'])
    expect('Clear at the lowercase question cancels', 'CCOUT' not in m.appvars)
    m = machine([NEWKEY, ENTER, QUIT], [])
    expect('New key is a stub that points to the PC script', 'MAKE KEYS ON PC' in shown(m), shown(m))
    m = machine([CLEAR], [])
    expect('Clear quits, home screen cleared, run indicator off', m.home == {} and not m.run_indicator)


if __name__ == '__main__':
    unit()
    sending()
    receiving()
    qr_engine_reads_ccout()
    menus()
    print('\n%s' % ('ALL PASSED' if not failures else '%d FAILED' % len(failures)))
    sys.exit(1 if failures else 0)
