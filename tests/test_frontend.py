"""Menu-flow tests for the BASIC front end (src/QR.basic.txt),
run in tibasic. Notes: list of names in Str3, the chosen name in Str2.

tibasic can't run assembly, so `Asm(prgmθQR` becomes `prgmθQR` and a BASIC
stand-in plays the engine (C is the command, docs/API.md):
  C=2 (list notes)  copies Str9 to Str3 and returns Z, the note count the test set up
  C=0 (check)       returns W, set up by the test (2*length+alnum, or 65533 for a bad character),
                    and sets B to X if X isn't 0 (the bad character's position, or a
                    note's first non-ASCII one; like the engine, it leaves B alone
                    otherwise)
  C=1 (draw)        returns G (0 = drawn)
Each call is logged in L₁ as 100000N+1000V+100M+10C+I (and O, the count to skip, in L₂),
read back as (C, I, V, M, N), so a test can check what the front end asked for, in order. Key presses (getKey) are scripted too;
running out raises, so a stuck key loop can't hang the suite.

  PYTHONUTF8=1 python tests/test_frontend.py
"""
import sys

from test_basic import (ROOT, TIProgram, Environment, ScriptedConsole, TiList, install,
                        get_token, CHAR_TABLE, expect, failures)
from core import TiString

MESSAGE, NOTEFOLIO, SET_VERSION, MODE, EXIT = range(5)   # main menu
STUB = '''T+1→T
If T>20
Stop
100000N+1000V+100M+10C+I→L₁(T
O→L₂(T
If C=2
Str9→Str3
If X and not(C
X→B
G
If not(C
W
If C=2
Z'''                                                            # T>20: stop a runaway loop
NOTES = ['NOTE%d' % i for i in range(1, 13)]                    # 3 pages: 5, 5, 2
BAD = 65533


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


def run(choices, inputs, notes=(), check=0, encode=0, keys=(), warn=0):
    env = Environment(console=MenuLog(inputs=inputs, choices=choices, keys=keys))
    front = tokens((ROOT / "src" / "QR.basic.txt").read_text(encoding='utf-8').rstrip('\n'))
    assert front.count(b'\xbb\x6a\x5f\x5bQR') == 3                  # Asm(prgmθQR
    install(env, 'QR', front.replace(b'\xbb\x6a\x5f\x5bQR', b'\x5f\x5bQR'))
    install(env, 'θQR', tokens(STUB))
    for v in 'TNVOCI':
        setattr(env.numerics, v, 0.0)
    env.numerics.Z = float(len(notes))
    env.numerics.W = float(check)
    env.numerics.G = float(encode)
    env.numerics.X = float(warn)
    env.numerics.B = 7.0                                        # prgmQR must reset it
    names = ''.join(n.ljust(8) for n in notes)   # the engine's Str3: pages of 5, no more
    env.strings[8] = TiString.from_str(names + ' ' * (-len(names) % 40))
    env.lists[0] = TiList([0.0])
    env.lists[1] = TiList([0.0])
    env.submit([get_token(0x5F), *(CHAR_TABLE[c] for c in 'QR')])
    calls = [int(x) for x in env.lists[0].data][:int(env.numerics.T)]
    calls = [(c // 10 % 10, c % 10, c // 1000 % 100, c // 100 % 10, c // 100000) for c in calls]
    env.offsets = [int(x) for x in env.lists[1].data][:int(env.numerics.T)]
    return calls, env.console.menus, env


def case(name, choices, inputs, want_calls, want_menus, want_screen=(), avoid_screen=(),
         want_str2=None, want_offsets=None, want_str3=True, **kw):
    """want_calls: (C, I, V, M, N) per engine call; want_menus: option lists after the first
    main menu (blank-padded options stripped); want_screen: text that must appear on a
    home-screen frame captured at a Pause; want_str2: the note picked; want_str3=False: the
    list of names must be deleted by the end."""
    try:
        calls, menus, env = run(choices, inputs, **kw)
    except Exception as e:
        expect(name, False, repr(e))
        return
    got_menus = [[o.strip() for o in opts] for _, opts in menus[1:]]
    screens = '\n'.join(env.console.frames)
    str2 = env.strings[1] and str(env.strings[1]).strip()
    ok = (calls == want_calls and got_menus == want_menus and
          all(t in screens for t in want_screen) and not any(t in screens for t in avoid_screen) and
          (want_str2 is None or str2 == want_str2) and
          (want_offsets is None or env.offsets == want_offsets) and
          (want_str3 or not env.strings[2]))
    expect(name, ok, 'calls %r, offsets %r, menus %r, Str2 %r, Str3 %r, screens:\n%s'
           % (calls, env.offsets, got_menus, str2, env.strings[2], screens))


def main(mode='Auto'):
    return ['Message', 'NoteFolio', 'Set version', 'Mode:' + mode, 'Exit']


def page(n, notes=NOTES):
    """Menu n of the pager: 5 names (blank past the last), Next (blank on the last page), Back."""
    names = notes[5 * n:5 * n + 5]
    nxt = 'Next' if 5 * n + 5 < len(notes) else ''
    return names + [''] * (5 - len(names)) + [nxt, 'Back']


def check(i=0, v=0, m=0):
    """A check call (C=0) of Str1 (i=0) or a note (i=1); V and M are the user's settings."""
    return (0, i, v, m, 0)


def draw(n, v, m, i=0):
    """A draw call (C=1): N characters at version V in mode M (1 ASCII, 2 alphanumeric)."""
    return (1, i, v, m, n)


CHECKED = check()                              # a message, auto mode, auto version

if __name__ == '__main__':
    # messages: a check call, then the version from the check's length and mode
    case('alphanumeric message, auto version', [MESSAGE], ['ABCD'],
         [CHECKED, draw(4, 1, 2)], [], check=2 * 4 + 1)
    case('20 ASCII characters need version 2', [MESSAGE], ['A' * 20],
         [CHECKED, draw(20, 2, 1)], [], check=2 * 20)
    case('20 alphanumeric characters fit version 1', [MESSAGE], ['A' * 20],
         [CHECKED, draw(20, 1, 2)], [], check=2 * 20 + 1)
    case('a set version bigger than needed is kept', [SET_VERSION, MESSAGE], ['5', 'ABCD'],
         [check(v=5), draw(4, 5, 1)], [main()], check=2 * 4)
    case('an empty message is one empty code', [MESSAGE], [''], [CHECKED, draw(0, 1, 2)], [], check=1)
    # mode
    case('Mode cycles Auto, ASCII, Alnum, Auto', [MODE, MODE, MODE, EXIT], [],
         [], [main('ASCII'), main('Alnum'), main('Auto')])
    case('the mode is passed to the engine', [MODE, MESSAGE], ['ABCD'],
         [check(m=1), draw(4, 1, 1)], [main('ASCII')], check=2 * 4)
    # bad characters: an error screen, then back to the main menu
    case('bad char in a message', [MESSAGE, EXIT], ['ABCD'],
         [CHECKED], [main()], ['ERR:BAD CHAR', 'Char: C', 'Pos=3'], check=BAD, warn=3)
    case('forced alnum says NOT ALNUM', [MODE, MODE, MESSAGE, EXIT], ['AbCD'],
         [check(m=2)], [main('ASCII'), main('Alnum'), main('Alnum')],
         ['ERR:NOT ALNUM', 'Char: b', 'Pos=2'], check=BAD, warn=2)
    case('too long: an error, nothing encoded', [MESSAGE, EXIT], ['ABCD'],
         [CHECKED], [main()], ['ERR:TOO LONG', 'Max 32765 chars'], check=65532)
    # the check's errors leave the settings alone: the menu still says Auto, the version
    # stays as set
    case('after a check error the settings are unchanged', [SET_VERSION, MESSAGE, MESSAGE, EXIT],
         ['3', 'ABCD', 'ABCD'], [check(v=3), check(v=3)], [main(), main(), main()],
         ['ERR:BAD CHAR'], check=BAD, warn=1)
    # the engine's own errors: the code on the home screen; on the check, then the main menu
    case('engine error on the check: ERR:ENGINE with the code', [MESSAGE, EXIT], ['ABCD'],
         [CHECKED], [main()], ['ERR:ENGINE', 'Code=65535'], check=65535)
    case('engine error while drawing: ERR:ENGINE, then the program ends', [MESSAGE], ['ABCD'],
         [CHECKED, draw(4, 1, 2)], [], ['ERR:ENGINE', 'Code=65535'], check=2 * 4 + 1,
         encode=65535)

    # NoteFolio picker: menu options are 5 names, Next (5), Back (6)
    LISTED = [(2, 0, 0, 0, 0)]
    case('Back on the first page goes to the main menu, Str3 deleted', [NOTEFOLIO, 6, EXIT], [],
         LISTED, [page(0), main()], notes=NOTES, want_str3=False)
    case('Back goes back a page', [NOTEFOLIO, 5, 6, 6, EXIT], [],
         LISTED, [page(0), page(1), page(0), main()], notes=NOTES)
    case('Next is blank on the last page and does nothing', [NOTEFOLIO, 5, 5, 5, 6, 6, 6, EXIT], [],
         LISTED, [page(0), page(1), page(2), page(2), page(1), page(0), main()], notes=NOTES)
    case('one full page: Next is blank', [NOTEFOLIO, 5, 6, EXIT], [],
         LISTED, [page(0, NOTES[:5]), page(0, NOTES[:5]), main()], notes=NOTES[:5])
    case('two full pages: Next on the first only', [NOTEFOLIO, 5, 5, 6, 6, EXIT], [],
         LISTED, [page(0, NOTES[:10]), page(1, NOTES[:10]), page(1, NOTES[:10]), page(0, NOTES[:10]),
                  main()], notes=NOTES[:10])
    case('a blank slot on the last page stays there', [NOTEFOLIO, 5, 5, 3, 6, 6, 6, EXIT], [],
         LISTED, [page(0), page(1), page(2), page(2), page(1), page(0), main()], notes=NOTES)
    case('pick a note after paging back', [NOTEFOLIO, 5, 5, 6, 1], [],
         LISTED + [check(i=1), draw(12, 1, 1, i=1)], [page(0), page(1), page(2), page(1)],
         notes=NOTES, check=2 * 12, want_str2='NOTE7', want_str3=False)
    case('non-ASCII in a note: warning with the position, Pause, then encode', [NOTEFOLIO, 0], [],
         LISTED + [check(i=1), draw(12, 1, 1, i=1)], [page(0)], ['Non-ASCII chars', 'Pos=40'],
         notes=NOTES, check=2 * 12, warn=40)
    case('a plain note: no warning (B is reset before the check)', [NOTEFOLIO, 0], [],
         LISTED + [check(i=1), draw(12, 1, 1, i=1)], [page(0)], [], ['NON-ASCII'],
         notes=NOTES, check=2 * 12)
    case('bad char in a note (forced alnum): position only', [NOTEFOLIO, 0, EXIT], [],
         LISTED + [check(i=1)], [page(0), main()], ['ERR:BAD CHAR', 'Pos=40'], ['Char:'],
         notes=NOTES, check=BAD, warn=40)
    case('no notes', [NOTEFOLIO, 0, EXIT], [], LISTED, [['Back', 'Exit'], main()], want_str3=False)
    # too long for one code: always split, into even pieces at the smallest version that fits
    # one (or the set version); Enter/→ next,
    # ← back, Clear stops, Enter on the last ends
    NEXT, RIGHT, LEFT, CLEAR = 105, 26, 24, 45
    piece = lambda n: draw(n, 10, 1)           # 700 bytes: 3 pieces of 234, 234, 232 at v10
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
         [CHECKED, draw(334, 9, 2), draw(334, 9, 2), draw(332, 9, 2)], [], check=2 * 1000 + 1,
         keys=[NEXT] * 3, want_offsets=[0, 0, 334, 668])
    case('a set version keeps its size', [SET_VERSION, MESSAGE], ['2', 'A' * 70],
         [check(v=2), draw(24, 2, 1), draw(24, 2, 1), draw(22, 2, 1)], [main()], check=2 * 70,
         keys=[NEXT] * 3, want_offsets=[0, 0, 24, 48])

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
