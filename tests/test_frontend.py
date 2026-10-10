"""Menu-flow tests for the BASIC front end (src/QR.basic.txt), run in tibasic.

tibasic can't run assembly, so `Asm(prgmQRENGINE` becomes `prgmQRENGINE` and a BASIC
stand-in plays the engine:
  E=4 (list notes)  copies Str9 to Str4 and returns Z, the note count the test set up
  V=0 (check text)  returns W, set up by the test (2*length+alnum, or 32768+position)
  otherwise         returns G (0 = drawn)
Each call is logged in L₆ as 10000N+100V+10M+E, so a test can check what the front end
asked for, in order.

  PYTHONUTF8=1 python tests/test_frontend.py
"""
import sys

from test_basic import (ROOT, TIProgram, Environment, ScriptedConsole, TiList, install,
                        get_token, CHAR_TABLE, expect, failures)
from core import TiString

MESSAGE, NOTEFOLIO, BINARY, SET_VERSION, MODE, EXIT = range(6)   # main menu
STUB = '''T+1→T
If T>8
Stop
10000N+100V+10M+E→L₆(T
If E=4
Str9→Str4
G
If not(V
W
If E=4
Z'''                                                            # T>8: stop a runaway loop
NOTES = ['NOTE%d' % i for i in range(1, 13)]                    # 3 pages: 5, 5, 2
BAD = 32768


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


def run(choices, inputs, notes=(), check=0, encode=0, binary=None):
    env = Environment(console=MenuLog(inputs=inputs, choices=choices))
    front = tokens((ROOT / 'src' / 'QR.basic.txt').read_text(encoding='utf-8').rstrip('\n'))
    assert front.count(b'\xbb\x6a\x5fQRENGINE') == 3
    install(env, 'QR', front.replace(b'\xbb\x6a\x5fQRENGINE', b'\x5fQRENGINE'))
    install(env, 'QRENGINE', tokens(STUB))
    for v in 'TNV':
        setattr(env.numerics, v, 0.0)
    env.numerics.Z = float(len(notes))
    env.numerics.W = float(check)
    env.numerics.G = float(encode)
    env.strings[8] = TiString.from_str(''.join(n.ljust(8) for n in notes) + ' ' * 48)
    if binary is not None:
        env.user_lists['BIN'] = TiList([float(b) for b in binary])
    env.lists[5] = TiList([0.0])
    env.submit([get_token(0x5F), *(CHAR_TABLE[c] for c in 'QR')])
    calls = [int(x) for x in env.lists[5].data][:int(env.numerics.T)]
    calls = [(c // 10000, c // 100 % 100, c // 10 % 10, c % 10) for c in calls]
    return calls, env.console.menus, env


def case(name, choices, inputs, want_calls, want_menus, want_screen=(), avoid_screen=(),
         want_str5=None, **kw):
    """want_calls: (N, V, M, E) per engine call; want_menus: option lists after the first
    main menu (blank-padded options stripped); want_screen: text that must appear on a
    home-screen frame captured at a Pause; want_str5: the note picked."""
    try:
        calls, menus, env = run(choices, inputs, **kw)
    except Exception as e:
        expect(name, False, repr(e))
        return
    got_menus = [[o.strip() for o in opts] for _, opts in menus[1:]]
    screens = '\n'.join(env.console.frames)
    str5 = env.strings[4] and str(env.strings[4]).strip()
    ok = (calls == want_calls and got_menus == want_menus and
          all(t in screens for t in want_screen) and not any(t in screens for t in avoid_screen) and
          (want_str5 is None or str5 == want_str5))
    expect(name, ok, 'calls %r, menus %r, Str5 %r, screens:\n%s' % (calls, got_menus, str5, screens))


def main(mode='Auto'):
    return ['Message', 'NoteFolio', 'Binary (ʟBIN)', 'Set version', 'Mode:' + mode, 'Exit']


def page(n):
    names = NOTES[5 * n:5 * n + 5]
    return names + [''] * (5 - len(names)) + ['More', 'Back']


RTA = ['Resize', 'Truncate', 'Abort']
CHECKED = (0, 0, 0, 1)                         # the check call for a message in auto mode

if __name__ == '__main__':
    # messages: a check call, then the version from the check's length and mode
    case('alphanumeric message, auto version', [MESSAGE], ['ABCD'],
         [CHECKED, (4, 1, 0, 1)], [], check=2 * 4 + 1)
    case('20 ASCII characters need version 2', [MESSAGE], ['A' * 20],
         [CHECKED, (20, 2, 0, 1)], [], check=2 * 20)
    case('20 alphanumeric characters fit version 1', [MESSAGE], ['A' * 20],
         [CHECKED, (20, 1, 0, 1)], [], check=2 * 20 + 1)
    case('too long for a set version, Truncate', [SET_VERSION, MESSAGE, 1], ['1', 'A' * 20],
         [CHECKED, (17, 1, 0, 1)], [main(), RTA], check=2 * 20)
    case('too long for a set version, Resize', [SET_VERSION, MESSAGE, 0], ['1', 'A' * 20],
         [CHECKED, (20, 2, 0, 1)], [main(), RTA], check=2 * 20)
    case('binary skips the check', [BINARY], [], [(5, 1, 0, 2)], [], binary=range(5))
    # mode
    case('Mode cycles Auto, ASCII, Alnum, Auto', [MODE, MODE, MODE, EXIT], [],
         [], [main('ASCII'), main('Alnum'), main('Auto')])
    case('the mode is passed to the engine', [MODE, MESSAGE], ['ABCD'],
         [(0, 0, 1, 1), (4, 1, 1, 1)], [main('ASCII')], check=2 * 4)
    # bad characters: an error screen, then back to the main menu
    case('bad char in a message', [MESSAGE, EXIT], ['ABCD'],
         [CHECKED], [main()], ['ERR:BAD CHAR', 'Char: C', 'Position: 3'], check=BAD + 3)
    case('forced alnum says NOT ALNUM', [MODE, MODE, MESSAGE, EXIT], ['AbCD'],
         [(0, 0, 2, 1)], [main('ASCII'), main('Alnum'), main('Alnum')],
         ['ERR:NOT ALNUM', 'Char: b', 'Position: 2'], check=BAD + 2)
    case('bad char reported while encoding', [MESSAGE, EXIT], ['ABCD'],
         [CHECKED, (4, 1, 0, 1)], [main()], ['ERR:BAD CHAR', 'Char: D', 'Position: 4'],
         check=2 * 4, encode=BAD + 4)

    # NoteFolio picker: menu options are 5 names, More (5), Back (6)
    LISTED = [(0, 0, 0, 4)]
    case('Back on the first page goes to the main menu', [NOTEFOLIO, 6, EXIT], [],
         LISTED, [page(0), main()], notes=NOTES)
    case('Back goes back a page', [NOTEFOLIO, 5, 6, 6, EXIT], [],
         LISTED, [page(0), page(1), page(0), main()], notes=NOTES)
    case('More wraps from the last page to the first', [NOTEFOLIO, 5, 5, 5, 6, EXIT], [],
         LISTED, [page(0), page(1), page(2), page(0), main()], notes=NOTES)
    case('a blank slot on the last page stays there', [NOTEFOLIO, 5, 5, 3, 6, 6, 6, EXIT], [],
         LISTED, [page(0), page(1), page(2), page(2), page(1), page(0), main()], notes=NOTES)
    case('pick a note after paging back', [NOTEFOLIO, 5, 5, 6, 1], [],
         LISTED + [(0, 0, 0, 3), (12, 1, 0, 3)], [page(0), page(1), page(2), page(1)],
         notes=NOTES, check=2 * 12, want_str5='NOTE7')
    case('bad char in a note: position only', [NOTEFOLIO, 0, EXIT], [],
         LISTED + [(0, 0, 0, 3)], [page(0), main()], ['ERR:BAD CHAR', 'Position: 40'], ['Char:'],
         notes=NOTES, check=BAD + 40)
    case('no notes', [NOTEFOLIO, 0, EXIT], [], LISTED, [['Back', 'Exit'], main()])
    print('\nALL PASSED' if not failures else '\n%d FAILED' % len(failures))
    sys.exit(1 if failures else 0)
