"""Menu-flow tests for the BASIC front end (src/QR.basic.txt), run in tibasic.

tibasic can't run assembly, so `Asm(prgmθQR` becomes `prgmθQR` and a BASIC
stand-in plays the engine:
  E=4 (list notes)  copies Str9 to Str2 and returns Z, the note count the test set up
  V=0 (check text)  returns W, set up by the test (2*length+alnum, or 32768+position),
                    and sets B to X if X isn't 0 (a note's first non-ASCII position;
                    like the engine, it leaves B alone otherwise)
  otherwise         returns G (0 = drawn)
Each call is logged in L₆ as 10000N+100V+10M+E (and O, the count to skip, in L₅), so a
test can check what the front end asked for, in order. Key presses (getKey) are scripted too;
running out raises, so a stuck key loop can't hang the suite.

  PYTHONUTF8=1 python tests/test_frontend.py
"""
import sys

from test_basic import (ROOT, TIProgram, Environment, ScriptedConsole, TiList, install,
                        get_token, CHAR_TABLE, expect, failures)
from core import TiString

MESSAGE, NOTEFOLIO, BINARY, SET_VERSION, MODE, EXIT = range(6)   # main menu
STUB = '''T+1→T
If T>20
Stop
10000N+100V+10M+E→L₆(T
O→L₅(T
If E=4
Str9→Str2
If not(V
If X
X→B
G
If not(V
W
If E=4
Z'''                                                            # T>20: stop a runaway loop
NOTES = ['NOTE%d' % i for i in range(1, 13)]                    # 3 pages: 5, 5, 2
BAD = 32768


class MenuLog(ScriptedConsole):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.menus = []

    def menu(self):
        self.menus.append((str(self.env.menu.title), [str(o) for o in self.env.menu.options]))
        return super().menu()

    def read_key(self):
        if not self.keys:
            raise ValueError('ScriptedConsole: no key presses left')
        return self.keys.pop(0)


def tokens(text):
    p = TIProgram(name='T')
    p.load_string(text)
    return bytes(p.data)


def run(choices, inputs, notes=(), check=0, encode=0, binary=None, keys=(), warn=0):
    env = Environment(console=MenuLog(inputs=inputs, choices=choices, keys=keys))
    front = tokens((ROOT / 'src' / 'QR.basic.txt').read_text(encoding='utf-8').rstrip('\n'))
    assert front.count(b'\xbb\x6a\x5f\x5bQR') == 3                  # Asm(prgmθQR
    install(env, 'QR', front.replace(b'\xbb\x6a\x5f\x5bQR', b'\x5f\x5bQR'))
    install(env, 'θQR', tokens(STUB))
    for v in 'TNVO':
        setattr(env.numerics, v, 0.0)
    env.numerics.Z = float(len(notes))
    env.numerics.W = float(check)
    env.numerics.G = float(encode)
    env.numerics.X = float(warn)
    env.numerics.B = 7.0                                        # prgmQR must reset it
    env.strings[8] = TiString.from_str(''.join(n.ljust(8) for n in notes) + ' ' * 48)
    if binary is not None:
        env.user_lists['BIN'] = TiList([float(b) for b in binary])
    env.lists[5] = TiList([0.0])
    env.lists[4] = TiList([0.0])
    env.submit([get_token(0x5F), *(CHAR_TABLE[c] for c in 'QR')])
    calls = [int(x) for x in env.lists[5].data][:int(env.numerics.T)]
    calls = [(c // 10000, c // 100 % 100, c // 10 % 10, c % 10) for c in calls]
    env.offsets = [int(x) for x in env.lists[4].data][:int(env.numerics.T)]
    return calls, env.console.menus, env


def case(name, choices, inputs, want_calls, want_menus, want_screen=(), avoid_screen=(),
         want_str3=None, want_offsets=None, **kw):
    """want_calls: (N, V, M, E) per engine call; want_menus: option lists after the first
    main menu (blank-padded options stripped); want_screen: text that must appear on a
    home-screen frame captured at a Pause; want_str3: the note picked."""
    try:
        calls, menus, env = run(choices, inputs, **kw)
    except Exception as e:
        expect(name, False, repr(e))
        return
    got_menus = [[o.strip() for o in opts] for _, opts in menus[1:]]
    screens = '\n'.join(env.console.frames)
    str3 = env.strings[2] and str(env.strings[2]).strip()
    ok = (calls == want_calls and got_menus == want_menus and
          all(t in screens for t in want_screen) and not any(t in screens for t in avoid_screen) and
          (want_str3 is None or str3 == want_str3) and
          (want_offsets is None or env.offsets == want_offsets))
    expect(name, ok, 'calls %r, offsets %r, menus %r, Str3 %r, screens:\n%s'
           % (calls, env.offsets, got_menus, str3, screens))


def main(mode='Auto'):
    return ['Message', 'NoteFolio', 'Binary (ʟBIN)', 'Set version', 'Mode:' + mode, 'Exit']


def page(n):
    names = NOTES[5 * n:5 * n + 5]
    return names + [''] * (5 - len(names)) + ['More', 'Back']


CHECKED = (0, 0, 0, 1)                         # the check call for a message in auto mode

if __name__ == '__main__':
    # messages: a check call, then the version from the check's length and mode
    case('alphanumeric message, auto version', [MESSAGE], ['ABCD'],
         [CHECKED, (4, 1, 0, 1)], [], check=2 * 4 + 1)
    case('20 ASCII characters need version 2', [MESSAGE], ['A' * 20],
         [CHECKED, (20, 2, 0, 1)], [], check=2 * 20)
    case('20 alphanumeric characters fit version 1', [MESSAGE], ['A' * 20],
         [CHECKED, (20, 1, 0, 1)], [], check=2 * 20 + 1)
    case('a set version bigger than needed is kept', [SET_VERSION, MESSAGE], ['5', 'ABCD'],
         [CHECKED, (4, 5, 0, 1)], [main()], check=2 * 4)
    case('an empty message is one empty code', [MESSAGE], [''], [CHECKED, (0, 1, 0, 1)], [], check=1)
    case('binary skips the check', [BINARY], [], [(5, 1, 0, 2)], [], binary=range(5))
    # mode
    case('Mode cycles Auto, ASCII, Alnum, Auto', [MODE, MODE, MODE, EXIT], [],
         [], [main('ASCII'), main('Alnum'), main('Auto')])
    case('the mode is passed to the engine', [MODE, MESSAGE], ['ABCD'],
         [(0, 0, 1, 1), (4, 1, 1, 1)], [main('ASCII')], check=2 * 4)
    # bad characters: an error screen, then back to the main menu
    case('bad char in a message', [MESSAGE, EXIT], ['ABCD'],
         [CHECKED], [main()], ['ERR:BAD CHAR', 'Char: C', 'Pos=3'], check=BAD + 3)
    case('forced alnum says NOT ALNUM', [MODE, MODE, MESSAGE, EXIT], ['AbCD'],
         [(0, 0, 2, 1)], [main('ASCII'), main('Alnum'), main('Alnum')],
         ['ERR:NOT ALNUM', 'Char: b', 'Pos=2'], check=BAD + 2)
    case('too long: an error, nothing encoded', [MESSAGE, EXIT], ['ABCD'],
         [CHECKED], [main()], ['ERR:TOO LONG', 'Max 16383 chars'], check=65532)
    case('bad char reported while encoding', [MESSAGE, EXIT], ['ABCD'],
         [CHECKED, (4, 1, 0, 1)], [main()], ['ERR:BAD CHAR', 'Char: D', 'Pos=4'],
         check=2 * 4, encode=BAD + 4)

    # NoteFolio picker: menu options are 5 names, More (5), Back (6)
    LISTED = [(0, 0, 0, 4)]
    case('Back on the first page goes to the main menu', [NOTEFOLIO, 6, EXIT], [],
         LISTED, [page(0), main()], notes=NOTES)
    case('Back goes back a page', [NOTEFOLIO, 5, 6, 6, EXIT], [],
         LISTED, [page(0), page(1), page(0), main()], notes=NOTES)
    case('More does nothing on the last page', [NOTEFOLIO, 5, 5, 5, 6, 6, 6, EXIT], [],
         LISTED, [page(0), page(1), page(2), page(2), page(1), page(0), main()], notes=NOTES)
    case('a blank slot on the last page stays there', [NOTEFOLIO, 5, 5, 3, 6, 6, 6, EXIT], [],
         LISTED, [page(0), page(1), page(2), page(2), page(1), page(0), main()], notes=NOTES)
    case('pick a note after paging back', [NOTEFOLIO, 5, 5, 6, 1], [],
         LISTED + [(0, 0, 0, 3), (12, 1, 0, 3)], [page(0), page(1), page(2), page(1)],
         notes=NOTES, check=2 * 12, want_str3='NOTE7')
    case('non-ASCII in a note: warning with the position, Pause, then encode', [NOTEFOLIO, 0], [],
         LISTED + [(0, 0, 0, 3), (12, 1, 0, 3)], [page(0)], ['Non-ASCII chars', 'Pos=40'],
         notes=NOTES, check=2 * 12, warn=40)
    case('a plain note: no warning (B is reset before the check)', [NOTEFOLIO, 0], [],
         LISTED + [(0, 0, 0, 3), (12, 1, 0, 3)], [page(0)], [], ['NON-ASCII'],
         notes=NOTES, check=2 * 12)
    case('bad char in a note (forced alnum): position only', [NOTEFOLIO, 0, EXIT], [],
         LISTED + [(0, 0, 0, 3)], [page(0), main()], ['ERR:BAD CHAR', 'Pos=40'], ['Char:'],
         notes=NOTES, check=BAD + 40)
    case('no notes', [NOTEFOLIO, 0, EXIT], [], LISTED, [['Back', 'Exit'], main()])
    # too long for one code: always split, into even pieces at the smallest version that fits
    # one (or the set version); Enter/→ next,
    # ← back, Clear stops, Enter on the last ends
    NEXT, RIGHT, LEFT, CLEAR = 105, 26, 24, 45
    piece = lambda n: (n, 10, 0, 1)            # 700 bytes: 3 pieces of 234, 234, 232 at v10
    case('split 700 bytes into 3 at version 10', [MESSAGE], ['A' * 700],
         [CHECKED, piece(234), piece(234), piece(232)], [], check=2 * 700,
         keys=[NEXT] * 3, want_offsets=[0, 0, 234, 468])
    case('← goes back a code', [MESSAGE], ['A' * 700],
         [CHECKED] + [piece(234)] * 4 + [piece(232)], [], check=2 * 700,
         keys=[NEXT, LEFT, NEXT, NEXT, NEXT], want_offsets=[0, 0, 234, 0, 234, 468])
    case('← on the first code and → on the last do nothing', [MESSAGE], ['A' * 700],
         [CHECKED, piece(234), piece(234), piece(232)], [], check=2 * 700,
         keys=[LEFT, RIGHT, RIGHT, RIGHT, CLEAR], want_offsets=[0, 0, 234, 468])
    case('Clear stops', [MESSAGE], ['A' * 700], [CHECKED, piece(234)], [],
         check=2 * 700, keys=[CLEAR], want_offsets=[0, 0])
    case('alphanumeric splits by the alnum table', [MESSAGE], ['A' * 1000],
         [CHECKED, (334, 9, 0, 1), (334, 9, 0, 1), (332, 9, 0, 1)], [], check=2 * 1000 + 1,
         keys=[NEXT] * 3, want_offsets=[0, 0, 334, 668])
    case('a set version keeps its size', [SET_VERSION, MESSAGE], ['2', 'A' * 70],
         [CHECKED, (24, 2, 0, 1), (24, 2, 0, 1), (22, 2, 0, 1)], [main()], check=2 * 70,
         keys=[NEXT] * 3, want_offsets=[0, 0, 24, 48])
    case('ʟBIN splits too', [BINARY], [], [(200, 9, 0, 2), (199, 9, 0, 2)], [],
         binary=[7] * 399, keys=[NEXT] * 2, want_offsets=[0, 200])

    def counter(page, pages, version=0):
        """The fraction drawn for code `page` of `pages` (the stand-in draws no QR code)."""
        cap = (17 if version == 1 else 321)
        L = cap * (pages - 1) + 1
        _, _, env = run([SET_VERSION, MESSAGE], [str(version), 'A' * L], check=2 * L,
                        keys=[NEXT] * (page - 1) + [CLEAR])
        lit = {(r, c) for r in range(64) for c in range(96) if env.graph.get(r, c)}
        dj, dp = len(str(pages)), len(str(page))
        # right-aligned: ink ends at x=93 (94 is the last digit's blank column, 95 is reserved)
        bar = {(31, c) for c in range(95 - 4 * dj, 94)}
        top = {c for r, c in lit if r < 31}
        bottom = {c for r, c in lit if r > 31}
        ok = (bar <= lit and all(25 <= r <= 37 and 95 - 4 * dj <= c <= 93 for r, c in lit) and
              min(bottom) < 95 - 4 * dj + 2 and max(bottom) == 93 and
              top <= set(range(95 - 4 * dp, 94)) and min(top) < 95 - 4 * dp + 2 and
              not {r for r, c in lit} & {30, 32})
        expect('counter %d/%d: at the right edge, digits lined up, bar under it' % (page, pages),
               ok, sorted(lit))
    counter(1, 3)
    counter(3, 12)
    counter(12, 12)
    counter(5, 100, version=1)                 # 3 digits needs a small set version
    print('\nALL PASSED' if not failures else '\n%d FAILED' % len(failures))
    sys.exit(1 if failures else 0)
