# TI-83+ QR code generator: TI-BASIC front end + Axe engine

This project started in a claude.ai chat and moved here. That chat isn't available, so this file
and `docs/design.md` (imported at the bottom) carry what was built and decided. Read both first.

## Where things stand

- The release is the QR-only set (no encryption): `src/QR.basic.txt` (BASIC front end) +
  `src/QRSRC.axe.txt` (Axe engine, compiled on-calc into prgmθQR), built to `build/QR.8xp` and
  `build/QRSRC.8xp`. `src/_theta_QR.z80` is the Z80 port of the engine; the user has decided
  it will be the release's engine (design.md item 49), once archived notes and the note list
  are tried on the calculator. The pure-BASIC set (prgmQRBASIC + prgmθQRBIT) was submitted to ticalc.org; the
  Axe/Z80 release hasn't been submitted yet.
- The older set (BASIC front end + engine without the note list + a separate Axe note picker,
  prgmθNOTES) is frozen in `src/legacy/`: built to `build/legacy/` and still tested, but not
  maintained, so a fix to the release's engine isn't repeated there. It uses the same program
  names, so only one set can be on the calculator at a time. The repo as it was before this
  layout is the tag `before-restructure`.
- **The user edited prgmQR by hand on the calculator** (the old main set, now
  `src/legacy/QR.basic.txt`). Their QR.8xp supersedes it. If that still matters:
  `python tools/build.py decompile <their QR.8xp> -o src/legacy/QR.basic.txt`, then `git diff`,
  and keep their changes. Ask before reverting anything of theirs.
- No code has run on real hardware except by the user. They compile with Axe and report back.

## Layout

| Path | What |
| --- | --- |
| `src/QR.basic.txt` | TI-BASIC front end of the release, in tivars' text format: menus, version pick, splitting, a 5-per-page `Menu(` pager for Notefolio notes (names in Str3, the chosen name in Str2) |
| `src/QRSRC.axe.txt` | Axe engine of the release, Unicode text with Axe token spellings (`→ ʳ L₁ r₁ · ᴇ Y₁`). E=1 Str1, E=2 a note, E=3 lists the notes |
| `src/_theta_QR.z80` | the Z80 port of prgmθQR (3289 bytes): everything the Axe engine does, E=1-3 (all of `test_engine.py` and `test_notefolio.py` pass with `--asm`); to be the release's engine; build.py assembles it with spasm-ng from `tools/spasm/` (gitignored: `spasm64.exe` + `ti83plus.inc`, v0.5-beta.3) or PATH, else skips it, to `build/_theta_QR.8xp` plus `_theta_QR.lab` (its labels, for the tests) |
| `docs/asm_port.md` | plan for rewriting the engine in Z80 assembly: spasm-ng, a Z80-emulator harness with axesim's `Machine` interface so the existing tests run unchanged, milestones, decisions made while porting. Milestones 1-9 done (1-7 also on the calculator) |
| `tools/z80sim.py` | `AsmMachine`: runs a compiled `.8xp` in the `z80` package's emulator with axesim's `Machine` interface (a real VAT, flash pages read through port 6, bcalls in Python, junk in registers after each, strict memory/ports/stack/IY checks; `call(label)` runs one routine); `tests/test_z80sim.py` checks the harness |
| `docs/API.md` | how other programs call prgmθQR (variables, return values, capacity, a tested example) |
| `docs/readme.txt` | the release's user guide (the root `readme.txt` is the pure-BASIC set's) |
| `src/legacy/` | the frozen older set: `QR.basic.txt`, `QRSRC.axe.txt` (E=1-3, no note list) and `NOTESSRC.axe.txt` (prgmθNOTES: menu of Notefolio notes, name → Str2; Ans 1 picked, 0 cancelled, 2 none). Interface in `docs/legacy/API.md`; tests `tests/test_legacy_notefolio.py`, `tests/test_legacy_frontend.py` and `test_engine.py --legacy`; built to `build/legacy/` |
| `build/` | generated, ready-to-send `.8xp` files (ignored by Git; rebuild with `build.bat`) |
| `tools/build.py` | builds everything; `decompile` turns any `.8xp` back into text |
| `tools/axe_tokens.json` | Axe 1.2.1 token table (from TokenIDE's AxeTokens.xml by Runer112; reuse permitted) |
| `tools/axesim.py` | interpreter for the Axe subset the engine uses; the tests run the engine in it |
| `tests/` | `test_engine.py` (modes 0-2), `test_notefolio.py` (notes, E=3 list), `test_frontend.py` (menus), `qrtest.py` helpers |
| `tests/data/TEST.8xv` | a real Notefolio file saved by the user's calculator (archived) |
| `originals/` | the user's original pure-BASIC programs (QR, QRCW, QRBIT, QRECC, QRDRAW) |
| `src/QRBASIC.basic.txt`, `src/_theta_QRBIT.basic.txt` | the pure-BASIC generator, cleaned up: prgmQRBASIC (menus, codewords, ECC, drawing in one) + prgmθQRBIT (bit appender); built to `build/` with everything else; its readme is the root `readme.txt` |
| `src/XORTEST.basic.txt` | the user's XOR speed test (TI-84+: startTmr): pick complex, ʟXOR table or logical xor, run it N times on one random pair, show the seconds and the result (design.md item 40). Any `src/*.basic.txt` is built: default tokenizing unless listed in `MAX_MODE`, header comment from `BASIC_COMMENTS` (else "TI-BASIC program") |
| `tests/test_basic.py` | runs build/QRBASIC.8xp and _theta_QRBIT.8xp in the user's TI-BASIC emulator `../tibasic`; `tests/data/basic/` has ʟGFL/ʟGFX |
| `tools/txt2note.py` | PC tool: text file (UTF-8) → NoteFolio note `.8xv` (archived unless `--ram`; name from the file name or `-n`; Enter, `[`, `$`, θ, accents, Greek etc. mapped to calculator codes, curly quotes/dashes/tabs to ASCII, other characters refused or `--replace`d); `tests/test_txt2note.py` |
| `src/LOREMSRC.axe.txt` | test tool (Axe, compiles to prgmLOREM): writes note LOREM, lorem ipsum ×N (OS var N, ≤100): deletes an old LOREM first (`DelVar`), archives the new one; `tests/test_lorem.py` |
| `src/CHATSRC.axe.txt` | CodeChat prototype (Axe, compiles to prgmCODECHAT): encrypted messages as digits, AES-SIV, keyring appvar CCKEYS, counter CCSTATE, output note CCOUT; design.md "CodeChat". `tools/codechat.py` = PC side (keyrings, reference encrypt/decrypt); `tests/test_codechat.py`. The release's prgmQR lists CCOUT like any note, so it draws CodeChat's output |
| `src/UNPROSRC.axe.txt` | tool (Axe, compiles to prgmUNPROT): unprotects the program named in Str1 (VAT type 06h → 05h; `prgm` prefix allowed, must be in RAM) so TI Connect will copy an Axe-compiled program off the calculator; `tests/test_unprot.py` |
| `src/SPEEDSRC.axe.txt` | test tool (Axe, compiles to prgmSPEED): bar sweep + FPS (84+ clock port 45h), MODE toggles Full/Normal, shows port 20h speed at start; leaves the speed set. Hardware-only (Asm( port reads), not simulated |

## Commands

```
pip install -r requirements.txt          # tivars, qrcode, zxing-cpp, pillow, cryptography, z80
python tools/build.py                    # -> build/QR.8xp, build/QRSRC.8xp, ... (build.bat does the same, for double-clicking)
python tests/run_all.py                  # every suite but test_basic, in parallel (~30 s); --quick, --basic
python tests/test_engine.py --quick      # drop --quick for the full sweep (~30 s)
python tests/test_notefolio.py           # notes and the E=3 list (PYTHONUTF8=1)
python tests/test_frontend.py            # front-end menus; needs ../tibasic and PYTHONUTF8=1
python tests/test_basic.py --quick       # pure-BASIC set; same needs; minutes (see the workflow)
python tests/test_lorem.py               # the LOREM note maker
python tools/txt2note.py notes.txt       # -> NOTES.8xv, a NoteFolio note (-n NAME, -o OUT, --ram, --replace ?)
python tests/test_txt2note.py            # the text → note converter
python tests/test_unprot.py              # the UNPROT tool
python tests/test_codechat.py            # CodeChat (AES/CMAC vectors, sends vs the PC reference, receives)
python tools/codechat.py loopkey         # build/CCKEYS.8xv test keyring (LOOP0/LOOP1, one random key)
python tests/test_engine.py --asm        # the Z80 port (build first)
python tests/test_notefolio.py --asm     # its notes and note list (PYTHONUTF8=1)
python tests/test_z80sim.py              # the Z80 harness itself
python tests/test_engine.py --quick --legacy   # the frozen older set: also test_legacy_notefolio.py, test_legacy_frontend.py
python tools/build.py decompile build/QRSRC.8xp
```

Workflow for every change: edit `src/` → build → `python tests/run_all.py` → give the user
`build/*.8xp`. The user is focused on the Axe/hybrid sets and considers the pure-BASIC set
stable: run `test_basic.py` (or `run_all.py --basic`) only when `src/QRBASIC.basic.txt` or
`src/_theta_QRBIT.basic.txt` (or the lists they use) change.
`build.py` strips the Axe sources' comments (all but the `.NAME` line) and blank lines, refuses
to write QRSRC.8xp if tokenizing changes any code line, and fixes the header
(product ID byte 0 like TI Connect files; tivars writes 13h).

## How the user runs it

TI-83+ family, Axe Parser 1.2.2. Send QR and QRSRC, compile QRSRC in Axe with Options → shell
"No Shell" (the `.θQR` header line names the output), run prgmQR. (The legacy set also needs
NOTESSRC, compiled the same way: `.θNOTES`.) Running prgmθQR
needs free RAM at least its compiled size (`Asm(` copies it to userMem each call), so engine
size is RAM the user must keep free; static buffers inside the program cost it too. Old QRCW/QRBIT/QRECC/
QRDRAW and lists ʟGFL/ʟGFX/ʟCW are obsolete for it. The pure-BASIC set (`build/`: prgmQRBASIC,
prgmθQRBIT) still uses ʟGFL/ʟGFX/ʟCW, plus ʟXOR (nibble XOR table) when the XOR table option
is on; the build generates GFL.8xl, GFX.8xl and XOR.8xl in `build/` (GFL/GFX are byte-identical
to the user's, `tests/data/basic/`, apart from the comment), and ʟQROPT (4 options; `SetUpEditor QROPT` creates it, a bare
`SetUpEditor` then restores the list editor to L1-L6), and uses Str2/Str3 and L₁-L₅; at the end it empties L₁-L₆ (ClrList), keeping
ʟCW (Redraw draws it), Str2 (the working table, handy when testing) and Str3 (the ASCII fix option may supply it).

File names spell θ as `_theta_` (TI Connect's convention; it rejects a real θ in a file name):
`src/_theta_QRBIT.basic.txt` builds `build/_theta_QRBIT.8xp`, program θQRBIT.

build.py warns about TI-84+ commands (startTmr: the program won't run on a TI-83+) and refuses
color calculator tokens (max munch turned "Redraw" into the CE token Red; write `R\edraw`).
It also refuses lowercase letters outside a string (`check_letters`): a misspelled command such
as `checkTimer(` tokenizes as letters and would only fail on the calculator.
QRBASIC and θQRBIT are tokenized in tivars "max" mode (`MAX_MODE` in build.py; QR uses the default) (tokens inside strings, as the drawing's r₁ strings
need), so a string wanting single characters escapes them: `<\=>`, `[\\]`, `|~` (the tilde
token). `build.py` also teaches tivars the `π` spelling, which version 1.1.1 can't tokenize.

## Engine interface (BASIC sets OS variables, runs `Asm(prgmθQR)`, reads Ans)

prgmQR's NoteFolio entry calls E=3 for the list of names (in Str3), pages through them with
`Menu(` and puts the chosen name in Str2, then uses E=2. (The legacy set ran
`Asm(prgmθNOTES)` for the name instead; its engine has E=1 Str1, 2 ʟBIN, 3 a note.)

| E | Source |
| --- | --- |
| 1 | text in Str1 (tokens) |
| 2 | text of the Notefolio note named in Str2 (calculator character codes) |
| 3 | not an encoding: Ans = number of notes, Str3 = their names, 8 characters each, padded (docs/API.md) |

A missing OS variable reads as 0 (subroutine `GV`). For E=1-2 the engine reads `V` and `M` (mode: 0 auto, 1 ASCII, 2 alphanumeric). `V=0` only checks the text: Ans = 2·length + 1 if it will be encoded alphanumeric, +0 for
ASCII (length ≤ 32765). `V`=1-11 also reads `O` (count to skip first, for split messages) and `N` (count to encode; the engine clamps it to the input length, but
BASIC must keep it within the version's capacity: the engine only caps it at 468 so a bad N
can't write past L₁), draws, and returns 0. The check returns 65533, with the position in OS var B, if a character can't be encoded
(a Str1 token with no ASCII equivalent, or not alphanumeric when M=2). A note in byte mode never
fails: its bytes go out as calculator codes (θ/⁴/Enter swapped with `[`/`$`/newline), and the
check stores the first non-ASCII position in OS var B, which prgmQR zeroes first. 65532 from the check call if the text is longer
than 32765 (2·32765+1 stays below the error codes), and 65535 for bad parameters or a missing input.
Auto picks alphanumeric when every character allows it; the engine never writes M: prgmQR
sets M from the check's Ans bit (`If not(M:1+K-2L→M`) so the draw calls use that mode, and a
draw with M=0 decides by itself. prgmQR keeps the menu's mode in D and copies it to M before
each check. (A, the old
way of passing the decision back, is gone.) Always centered, EC level L, mask 0.
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
- `ElseIf c` / `Else!If c` (the Else and If tokens on one line) chain conditions in one block
  with one End; use them instead of an If that is an Else's whole body. axesim supports them.
- `ReturnIf c` / `Return!If c` instead of `If c` / `Return` / `End` (a Z80 conditional `ret`:
  3 bytes instead of 6). `Fill(PTR,SIZE,0)` instead of a loop storing zeros (SIZE must be
  more than 1). `e^(n)` is 2^n (axesim refuses n > 15).
- Comments start with `.`; a line starting with `...` opens a multi-line comment. In this
  project comments are whole lines only (axesim skips lines starting with `.`; build.py refuses
  `...` blocks), and build.py strips them all, plus blank lines, except line 1 (the `.NAME`
  header that names Axe's output). So comments cost nothing on the calculator and can use any
  characters.
- Write names as their tokens: `GDB1`, `Str1`, `L₁`, `"varE"` (`var` is the u token). The
  tokenizer does this from the spellings; plain letters in code would be variables.
- Comments too (the user's preference): `Str1`, `ʟBIN`, `L₁`, `r₁`, `Y₁`, `Ans`, `prgmQR`, `→`,
  `⁻` rather than spelling them out (STR1, L1, R1). Normal sentence case, not all caps. Explain
  the cryptic parts (unsigned wraparound tricks, left-to-right expressions, table layouts,
  memory offsets, the algorithm a loop implements); the full history belongs in docs/design.md.
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
