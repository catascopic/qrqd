"""Menu-flow tests for the BASIC front end (src/QR.basic.txt), run in tibasic.

tibasic can't run assembly, so `Asm(prgmQRENGINE` becomes `prgmQRENGINE` and a BASIC
stand-in plays the engine: encoding with safe mode on reports a bad character at position
3, otherwise success; listing notes (E=4) copies Str9 to Str4 and returns Z, the count the
test set up; measuring a note (E=5) returns 12. Each call is logged in L₆ as
10000N+100V+10S+E, so a test can check which modes and settings the front end asked for.

  PYTHONUTF8=1 python tests/test_frontend.py
"""
import sys

from test_basic import (ROOT, TIProgram, Environment, ScriptedConsole, TiList, install,
                        get_token, CHAR_TABLE, expect, failures)
from core import TiString

ASCII, NOTEFOLIO, ALNUM, BINARY, SET_VERSION, EXIT = range(6)   # main menu
STUB = '''T+1→T
If T>8
Stop
10000N+100V+10S+E→L₆(T
If E=4
Str9→Str4
3(S=1
If E=4
Z
If E=5
12'''                                                           # T>8: stop a runaway loop
NOTES = ['NOTE%d' % i for i in range(1, 13)]                    # 3 pages: 5, 5, 2


class MenuLog(ScriptedConsole):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.menus = []

    def menu(self):
        self.menus.append((str(self.env.menu.title), [str(o) for o in self.env.menu.options]))
        return super().menu()


def tokens(text):
    p = TIProgram(name='T')
    p.load_string(text)
    return bytes(p.data)


def run(choices, inputs, notes=()):
    env = Environment(console=MenuLog(inputs=inputs, choices=choices))
    front = tokens((ROOT / 'src' / 'QR.basic.txt').read_text(encoding='utf-8').rstrip('\n'))
    assert front.count(b'\xbb\x6a\x5fQRENGINE') == 3
    install(env, 'QR', front.replace(b'\xbb\x6a\x5fQRENGINE', b'\x5fQRENGINE'))
    install(env, 'QRENGINE', tokens(STUB))
    for v in 'TNVS':
        setattr(env.numerics, v, 0.0)
    env.numerics.Z = float(len(notes))
    env.strings[8] = TiString.from_str(''.join(n.ljust(8) for n in notes) + ' ' * 48)
    env.lists[5] = TiList([0.0])
    env.submit([get_token(0x5F), *(CHAR_TABLE[c] for c in 'QR')])
    calls = [int(x) for x in env.lists[5].data][:int(env.numerics.T)]
    calls = [(c // 10000, c // 100 % 100, c // 10 % 10, c % 10) for c in calls]
    return calls, env.console.menus, env


def case(name, choices, inputs, want_calls, want_menus, notes=(), want_str5=None):
    """want_calls: (N, V, S, E) per engine call; want_menus: option lists after the main menu
    (blank-padded options stripped); want_str5: the note picked."""
    try:
        calls, menus, env = run(choices, inputs, notes)
    except Exception as e:
        expect(name, False, repr(e))
        return
    got_menus = [[o.strip() for o in opts] for _, opts in menus[1:]]
    str5 = env.strings[4] and str(env.strings[4]).strip()
    expect(name, calls == want_calls and got_menus == want_menus and
           (want_str5 is None or str5 == want_str5),
           'calls %r, menus %r, Str5 %r' % (calls, got_menus, str5))


def page(n):
    names = NOTES[5 * n:5 * n + 5]
    return names + [''] * (5 - len(names)) + ['More', 'Back']


CA = ['Continue', 'Abort']
CUA = ['Continue', 'Use ASCII', 'Abort']
MAIN = ['ASCII', 'NoteFolio', 'Alphanumeric', 'Binary', 'Set version', 'Exit']

if __name__ == '__main__':
    case('ASCII bad char, Continue', [ASCII, 0], ['ABCD'],
         [(4, 1, 1, 1), (4, 1, 0, 1)], [CA])
    case('ASCII bad char, Abort', [ASCII, 1, EXIT], ['ABCD'],
         [(4, 1, 1, 1)], [CA, MAIN])
    case('alphanumeric bad char, Continue', [ALNUM, 0], ['ABCD'],
         [(4, 1, 1, 0), (4, 1, 0, 0)], [CUA])
    case('alphanumeric bad char, Use ASCII, Continue', [ALNUM, 1, 0], ['ABCD'],
         [(4, 1, 1, 0), (4, 1, 1, 1), (4, 1, 0, 1)], [CUA, CA])
    # 20 characters fit version 1 as alphanumeric (25) but not as ASCII (17)
    case('Use ASCII at a fixed version, Truncate', [SET_VERSION, ALNUM, 1, 1, 0], ['1', 'A' * 20],
         [(20, 1, 1, 0), (17, 1, 1, 1), (17, 1, 0, 1)],
         [MAIN, CUA, ['Resize', 'Truncate', 'Abort'], CA])

    # NoteFolio picker: menu options are 5 names, More (5), Back (6)
    LISTED = [(0, 0, 0, 4)]
    case('Back on the first page goes to the main menu', [NOTEFOLIO, 6, EXIT], [],
         LISTED, [page(0), MAIN], NOTES)
    case('Back goes back a page', [NOTEFOLIO, 5, 6, 6, EXIT], [],
         LISTED, [page(0), page(1), page(0), MAIN], NOTES)
    case('More wraps from the last page to the first', [NOTEFOLIO, 5, 5, 5, 6, EXIT], [],
         LISTED, [page(0), page(1), page(2), page(0), MAIN], NOTES)
    case('a blank slot on the last page stays there', [NOTEFOLIO, 5, 5, 3, 6, 6, 6, EXIT], [],
         LISTED, [page(0), page(1), page(2), page(2), page(1), page(0), MAIN], NOTES)
    case('pick a note after paging back', [NOTEFOLIO, 5, 5, 6, 1, 1, EXIT], [],
         LISTED + [(0, 0, 0, 5), (12, 1, 1, 3)], [page(0), page(1), page(2), page(1), CA, MAIN],
         NOTES, want_str5='NOTE7')
    case('no notes', [NOTEFOLIO, 0, EXIT], [], LISTED, [['Back', 'Exit'], MAIN])
    print('\nALL PASSED' if not failures else '\n%d FAILED' % len(failures))
    sys.exit(1 if failures else 0)
