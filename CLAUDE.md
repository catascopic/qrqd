# TI-83+ QR code generator: TI-BASIC front end + Axe engine

This project started in a claude.ai chat and moved here. That chat isn't available, so this file
and `docs/design.md` (imported at the bottom) carry what was built and decided. Read both first.

## Where things stand

- Delivered to the user and working in simulation: `build/QR.8xp` (BASIC) and `build/QRSRC.8xp`
  (Axe source, compiled on-calc into prgmθQR).
- **The user has since edited prgmQR by hand on the calculator.** Their QR.8xp supersedes
  `src/QR.basic.txt`. First task: `python tools/build.py decompile <their QR.8xp> -o src/QR.basic.txt`,
  then `git diff` (the first commit is the version from the chat) and keep their changes.
  Ask before reverting anything of theirs.
- No code has run on real hardware except by the user. They compile with Axe and report back.

## Layout

| Path | What |
| --- | --- |
| `src/QRSRC.axe.txt` | Axe engine source, Unicode text with Axe token spellings (`→ ʳ L₁ r₁ · ᴇ Y₁`) |
| `src/NOTESSRC.axe.txt` | Axe note picker, compiles to prgmθNOTES: menu of Notefolio notes, name → Str2 (Ans 1 picked, 0 cancelled, 2 none) |
| `docs/API.md` | how other programs call prgmθQR and prgmθNOTES (variables, return values, capacity, a tested example) |
| `src/QR.basic.txt` | TI-BASIC front end, in tivars' text format |
| `build/` | generated, ready-to-send `.8xp` files (ignored by Git; rebuild with `build.bat`) |
| `standalone/` | the QR-only release the user plans to publish (no encryption): `src/QR.basic.txt` + `src/QRSRC.axe.txt` as of commit 14b59a2 (= branch `basic_notefolio`: engine E=4 lists notes, BASIC 5-per-page Menu( pager), except the list of names is in Str3 and the chosen name in Str2. Same file and program names as the main set (prgmQR, prgmθQR), so only one set can be on the calculator at a time. Built to `build/standalone/`; `standalone/API.md`; tests in `standalone/tests/` |
| `tools/build.py` | builds both `.8xp`; `decompile` turns any `.8xp` back into text |
| `tools/axe_tokens.json` | Axe 1.2.1 token table (from TokenIDE's AxeTokens.xml by Runer112; reuse permitted) |
| `tools/axesim.py` | interpreter for the Axe subset the engine uses; the tests run the engine in it |
| `tests/` | `test_engine.py` (modes 0-2), `test_notefolio.py` (notes, and the picker), `qrtest.py` helpers |
| `tests/data/TEST.8xv` | a real Notefolio file saved by the user's calculator (archived) |
| `originals/` | the user's original pure-BASIC programs (QR, QRCW, QRBIT, QRECC, QRDRAW) |
| `src/QRBASIC.basic.txt`, `src/_theta_QRBIT.basic.txt` | the pure-BASIC generator, cleaned up: prgmQRBASIC (menus, codewords, ECC, drawing in one) + prgmθQRBIT (bit appender); built to `build/` with everything else |
| `tests/test_basic.py` | runs build/QRBASIC.8xp and _theta_QRBIT.8xp in the user's TI-BASIC emulator `../tibasic`; `tests/data/basic/` has ʟGFL/ʟGFX |
| `tests/test_frontend.py` | menu flows of `src/QR.basic.txt` in tibasic, with a BASIC stand-in for the engine |
| `src/LOREMSRC.axe.txt` | test tool (Axe, compiles to prgmLOREM): writes note LOREM, lorem ipsum ×N (OS var N, ≤100); `tests/test_lorem.py` |
| `src/SPEEDSRC.axe.txt` | test tool (Axe, compiles to prgmSPEED): bar sweep + FPS (84+ clock port 45h), MODE toggles Full/Normal, shows port 20h speed at start; leaves the speed set. Hardware-only (Asm( port reads), not simulated |

## Commands

```
pip install -r requirements.txt          # tivars, qrcode, zxing-cpp, pillow
python tools/build.py                    # -> build/QR.8xp, build/QRSRC.8xp (build.bat does the same, for double-clicking)
python tests/test_engine.py --quick      # drop --quick for the full sweep (a few minutes)
python tests/test_notefolio.py
python tests/test_frontend.py            # front-end menus; needs ../tibasic and PYTHONUTF8=1
python tests/test_basic.py --quick       # pure-BASIC set; same needs
python tests/test_lorem.py               # the LOREM note maker
python tests/test_engine.py --quick --standalone   # the standalone engine (modes 0-2)
python standalone/tests/test_notefolio.py          # its notes, E=4 list
python standalone/tests/test_frontend.py           # its menus (PYTHONUTF8=1)
python tools/build.py decompile build/QRSRC.8xp
```

Workflow for every change: edit `src/` → build → run the engine suites (and `test_frontend.py`
for BASIC changes) → give the user `build/*.8xp`.
`build.py` refuses to write QRSRC.8xp if tokenizing changes any code line, and fixes the header
(product ID byte 0 like TI Connect files; tivars writes 13h).

## How the user runs it

TI-83+ family, Axe Parser 1.2.2. Send QR, QRSRC and NOTESSRC, compile QRSRC and NOTESSRC in
Axe with Options → shell "No Shell" (the `.θQR`/`.θNOTES` header lines name the output), run prgmQR. Running prgmθQR
needs free RAM at least its compiled size (`Asm(` copies it to userMem each call), so engine
size is RAM the user must keep free; static buffers inside the program cost it too. Old QRCW/QRBIT/QRECC/
QRDRAW and lists ʟGFL/ʟGFX/ʟCW are obsolete for it. The pure-BASIC set (`build/`: prgmQRBASIC,
prgmθQRBIT) still uses ʟGFL/ʟGFX/ʟCW, plus ʟXOR (nibble XOR table) when the XOR table option
is on; the build generates GFL.8xl, GFX.8xl and XOR.8xl in `build/` (GFL/GFX are byte-identical
to the user's, `tests/data/basic/`, apart from the comment), and ʟQROPT (4 options; `SetUpEditor QROPT` creates it, a bare
`SetUpEditor` then restores the list editor to L1-L6), and overwrites Str2/Str3.

File names spell θ as `_theta_` (TI Connect's convention; it rejects a real θ in a file name):
`src/_theta_QRBIT.basic.txt` builds `build/_theta_QRBIT.8xp`, program θQRBIT.

build.py refuses BASIC tokens that need a color calculator (max munch turned "Redraw" into the
CE token Red; write `R\edraw`).
QRBASIC and θQRBIT are tokenized in tivars "max" mode (`MAX_MODE` in build.py; QR uses the default) (tokens inside strings, as the drawing's r₁ strings
need), so a string wanting single characters escapes them: `<\=>`, `[\\]`, `|~` (the tilde
token). `build.py` also teaches tivars the `π` spelling, which version 1.1.1 can't tokenize.

## Engine interface (BASIC sets OS variables, runs `Asm(prgmθQR)`, reads Ans)

prgmQR's NoteFolio entry runs `Asm(prgmθNOTES)` first (the picker writes the name to Str2),
then uses E=3.

| E | Source |
| --- | --- |
| 1 | text in Str1 (tokens) |
| 2 | bytes in list ʟBIN |
| 3 | text of the Notefolio note named in Str2 (calculator character codes) |

A missing OS variable reads as 0 (subroutine `GV`). For E=1-3 the engine reads `V` and `M` (mode: 0 auto, 1 ASCII, 2 alphanumeric; ignored for
ʟBIN). `V=0` only checks the text: Ans = 2·length + 1 if it will be encoded alphanumeric, +0 for
ASCII. `V`=1-11 also reads `O` (count to skip first, for split messages) and `N` (count to encode; the engine clamps it to the input length, but
BASIC must keep it within the version's capacity: the engine only caps it at 468 so a bad N
can't write past L₁), draws, and returns 0. The check returns 32768+k if character k can't be encoded
(a Str1 token with no ASCII equivalent, or not alphanumeric when M=2). A note in byte mode never
fails: its bytes go out as calculator codes (θ/⁴/Enter swapped with `[`/`$`/newline), and the
check stores the first non-ASCII position in OS var B, which prgmQR zeroes first. 65532 from the check call if the text is longer
than 16383 (2·16383+1 is the most Ans can carry), and 65535 for bad parameters or a missing input.
Auto picks alphanumeric when every character allows it. Always centered, EC level L, mask 0.
The engine draws into the graph buffer and calls DispGraph; BASIC handles display. BASIC checks
first, picks the version from the length and mode, then encodes.

## Axe rules that bite (Axe 1.2.2)

- Strict left-to-right evaluation, no precedence: `S-1-(K*2)`, never `S-1-K*2`. Parenthesize
  every comparison after the first in `and`/`or` chains: `A=1 or (B=2)`.
- All math is 16-bit unsigned. `and or xor` use only the low 8 bits; use `· ﹢ □` (plot-mark
  tokens) for 16-bit. `^` is modulo. `/` is unsigned division.
- `{P}` byte, `{P}ʳ` little-endian word. `Pxl-On(X,Y)ʳ`/`pxl-Test(X,Y)ʳ` = back buffer (L₃).
- `For(V,A,B)` checks the bound before the first pass; `Return` outside a subroutine ends the
  program; Returning from inside `For(V,..)`/`While` is fine. Subroutines share all globals.
- Comments start with `.`; a line starting with `...` opens a multi-line comment.
- Write names as their tokens: `GDB1`, `Str1`, `L₁`, `"varE"` (`var` is the u token). The
  tokenizer does this from the spellings; plain letters in code would be variables.
- OS names for GetCalc are OP1 bytes: type, name, 0 (e.g. `[015D42494E00]` = list BIN).
  `GetCalc` returns 0 for archived vars; archived data is read via `GetCalc(name,Y₁)` and `{Y₁+k}`.
- Free RAM: L₁ 714 bytes, L₃ 768 (back buffer), L₆ = graph buffer. See design.md for the map.

## TI-BASIC rules that bite

- Menu( allows at most 7 options. Labels are 1-2 characters, per program.
- Never `Goto` out of a `Then` block (leaks memory); the code uses single-line `If` + `Goto`.
- `If` conditions don't change Ans; the code relies on that.
- Before calling the engine: `FnOff`, `AxesOff`, `GridOff`, `PlotsOff`, `ClrDraw`, `DispGraph`, so the
  OS won't redraw (and erase) the graph when StorePic/DispGraph run afterwards.
- `65534` is stored in Ans right before `Asm(` so a missing engine shows as an error.
- A real `"` can't appear inside a program string, but users can type one at an Input prompt.

## Testing approach and its limits

The tests run the real engine source in `axesim.py` (left-to-right, 16-bit, byte/word memory,
VAT, archive files, graph buffers) and compare each drawn symbol with the `qrcode` library
(forced version, EC L, mask 0) plus a zxing-cpp decode. Not a valid reference: segno (adds an
extra 0x00 pad codeword). The simulator raises on anything with uncertain real behavior
(8-bit ops on values > 255, out-of-range pixels, ROM writes). Not verified on hardware: see the
risk list in design.md.

## Working with this user

- Wants BASIC for the interface (menus), Axe for math and graphics, cleanly separated.
- Wants ready-to-send `.8xp` files, tested before delivery, with plain explanations of changes.
- Asks for opinions on design choices; discuss before removing features.

@docs/design.md
