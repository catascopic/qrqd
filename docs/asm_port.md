# Plan: the standalone engine in Z80 assembly

Status: milestones 1-4 are done in the harness; 1-3 also on the user's calculator
(milestone 2 from the home screen: a valid call 0, V=12 and V=256 65535; milestone 3 through
prgmQR's bad-character screen and from the home screen: HELLO 11, A=B 6, forced alphanumeric
65533 with B = 2; all as in the harness).
`src/standalone/_theta_QR.z80` (1398 bytes) sets 15 MHz, reads E, V and M, rejects bad
ones, finds Str1 or ʟBIN (65535 if missing), and answers the check call (V=0): Str1's length
in tokens, the mode, and a bad character's position in B (65533). A draw call in auto mode
scans the text the same way, so a bad character fails it. A draw call (V=1-11) then reads N
and O and packs the data codewords into L₁ (mode, count, data, terminator, padding), and
answers 0 with nothing drawn (`NotYet`), as do a note (E=3) and the note list (E=4).
`tools/z80sim.py` runs it; `python tests/test_engine.py --asm` tests it, and `tests/test_z80sim.py` checks that
the harness catches each kind of mistake and models the OS routines as described below.

## Goal

Rewrite the standalone release's engine, prgmθQR (`src/standalone/QRSRC.axe.txt`), as a
hand-written Z80 assembly program with exactly the same interface (`docs/standalone/API.md`):
the same program name, the same OS variables in (E, V, M, N, O, Str1, Str2, ʟBIN), the same
answers out (Ans, B, Str3), and the same drawing. The standalone prgmQR stays as it is: it
keeps calling `Asm(prgmθQR)`. It is still the hybrid design (BASIC menus, a compiled engine),
just with assembly in place of Axe.

Keep the Axe engine in the repo as the reference until the assembly one has run on the
calculator. It is the specification: same algorithm, same tables, same memory map.

## Why try it

- **The tests would run the real program.** Today the tests run the Axe source in axesim,
  an interpreter written from Axe's documentation. If real Axe compiles something differently,
  the tests pass and the calculator fails ("never compiled by a real Axe" is the first item of
  design.md's risk list). With assembly, the tests would run the exact bytes the calculator
  runs, in a Z80 emulator. What's left to model is only the OS routines it calls.
- **Size, which is RAM.** `Asm(` copies the whole program into RAM to run it, so every byte
  is free RAM the user must have (the ERR:MEMORY in design.md item 12). Axe's output is 16-bit
  everywhere and brings its library along; most of the engine's values fit in 8 bits. The
  compiled Axe engine is roughly 6 KB (design.md item 33: 6267 bytes then). A guess for hand
  assembly is under half of that.
- **No Axe step for users.** The release would ship a ready-to-run program instead of
  QRSRC to compile, so people without Axe Parser can use it. That matters for publishing.
- **No Axe quirks.** No left-to-right math, no 8-bit `and`, no "parenthesize every
  comparison after the first".

What we give up: assembly is several times longer and much harder for the user to read,
review or change on the calculator; and a bug can freeze the calculator or clear its RAM.

## Tools

- **Assembler: spasm-ng** v0.5-beta.3 (2017, the newest release; github.com/alberthdev/spasm-ng):
  `spasm64.exe` and `ti83plus.inc` (from the same tag's `inc/`: bcall addresses, `saveSScreen`,
  `plotSScreen`, `progPtr`, `pTemp`, ...) in `tools/spasm/`, which is gitignored. `build.py`
  (`find_spasm`, `assemble`) looks there, then on PATH, and skips `*.z80` sources with a note
  when it finds neither. spasm writes raw bytes for a `.bin` output name; build.py writes the
  `.8xp` itself with tivars (`TIProtectedAsmProgram`, type 06h like Axe's output), because
  spasm names an `.8xp` after its file name (`_theta_QR.8xp` became program `_THETA_Q`).
- **Program format:** `.org userMem-2`, then `.db t2ByteTok, tasmCmp` (BBh 6Dh), code from
  9D95h. Code must stay below C000h, so at most 8,811 bytes, as for Axe's output (build.py
  refuses more).
- **Emulator: the `z80` package** (1.2.0 on PyPI, Ivan Kosarev's emulator: a C++ core with
  Python bindings; in requirements.txt). What it offers: `memory` (a 64 KB memoryview),
  breakpoints by address (used for rst 28h at 0028h and the exit address), port in/out
  callbacks, and a write callback for addresses marked `WRITE_MARK` (all of memory is marked,
  then the allowed areas unmarked). Exceptions raised in callbacks come out of `run()`.
  `run()` returns at every breakpoint and every 100,000 T-states (the end of its "frame"), so
  the harness calls it in a loop; `ticks_to_stop` bounds a run. It never raises an interrupt
  by itself. Speed: 100 million T-states in about 0.16 s, some 40 times a 15 MHz calculator.

## The test harness: a drop-in for axesim's `Machine`

The engine tests already describe everything the engine must do. They talk to axesim's
`Machine` through a small interface:

| Used by the tests | What it does |
| --- | --- |
| `set_real`, `get_real` | OS real variables (E, V, M, N, O, B) |
| `set_str`, `set_list` | Str1/Str2 (tokens), ʟBIN |
| `add_appvar(name, content, archived=)`, `add_vat_other`, `build_vat` | Notefolio notes in RAM or archive, other VAT entries (for E=4's list) |
| `run()` | run the engine |
| `ans`, `displays`, `os`, `mem`, `rd`, `arch_ptr` | Ans, the graph buffer at each display, the OS variables, memory |

So the plan is a new class with the same methods (say `tools/z80sim.py`, `AsmMachine`) that
loads `build/standalone/_theta_QR.8xp`, and an `--asm` switch in `test_engine.py --standalone`
and `test_standalone_notefolio.py` that picks it. Then the whole existing sweep (versions 1-11,
the three modes, splitting with O, bad characters and their positions, notes in RAM and archive,
the swaps, the B warning, the E=4 list) runs against the assembly program, unchanged, and each
symbol is still compared with the `qrcode` library and decoded by zxing-cpp.

What the harness has to provide:

- **Memory:** the TI-83+ RAM map. The program is copied to userMem; the OS variables live in
  RAM as the real OS stores them, with a real VAT (the engine walks the VAT itself for E=4, from
  `(progPtr)` down to `(pTemp)`).
- **OS calls:** trap `rst 28h` (bcall) and implement in Python the few routines the engine uses
  (below). Anything else raises, so an unexpected call is caught at once.
- **Archive:** flash pages, with what the engine needs for reading an archived note
  (`_LoadCIndPaged`, or port 6 page mapping at 4000h-7FFFh if we read flash directly).
- **Display:** record `plotSScreen` at each display call (axesim's `displays`).
- **Strictness, like axesim:** fail on writes to ROM or outside RAM, on running outside the
  program, on a stack that isn't back where it started at the final `ret`, on unknown OS calls,
  and if IY (the OS flags pointer) changes.

Built so far (`AsmMachine(program, model='84+', max_ticks=1.5e9)`):

- **Memory:** the code at userMem; writes allowed only to OP1-OP6, L₁, L₃, the graph buffer,
  the program, the stack below the return address (FE70h-FFDDh; the address itself sits at
  FFDEh) and the data of variables in RAM; ROM filled with FFh (rst 38h) and a breakpoint at
  0038h, so a jump into ROM raises.
- **Registers:** all start at 5A5Ah, and after every bcall every register the routine doesn't
  return is 5A5Ah again, the shadow registers too; the shadow registers are also reset every
  100,000 T-states, standing in for the OS's interrupt handler (assumed to use them). So the
  program can't count on a value surviving an OS call. At the end the stack, IY and
  interrupts-enabled are checked.
- **Ports:** port 2 reads the model (bit 7 set on a TI-84+), port 20h may be written on a
  TI-84+ only (`full`), any other port raises.
- **Variables and the VAT:** `set_real`, `set_str`, `set_list` (each with `archived=`) put the
  data in RAM from C000h, or for an archived one give it a flash page (0Bh) and a pointer into
  4000h-7FFFh, where nothing is mapped yet. `run()` writes the VAT first (`build_vat`): the
  symbol table from symTable (FE66h) down, 9-byte entries (type, T2, version, data pointer
  low, high, page, then a 3-byte name, going down), for reals and strings; then the program
  table from (progPtr) down to (pTemp), entries with a length byte and the name, for lists
  (assumed to live there, since their names are up to 6 bytes; test_unprot.py assumes it too),
  and later appvars. `vat_entries()` reads it back.
- **bcalls:** `_ChkFindSym` walks that VAT in memory (the symbol table by the 3 name bytes, the
  program table by name and kind): carry if missing, else HL = the entry, DE = the data, B =
  the page. `_SetXXXXOP2` (HL → OP2 as a float), `_OP2ToOP1`, `_StoAns` (sets `ans`),
  `_OP1Set0`. `calls` lists them in order, `ticks` is the run's T-states.
- **Single routines:** build.py writes the program's labels to `_theta_QR.lab` (spasm's `-L`,
  filtered to the names the source defines), and `call(label, de=..., ...)` runs one
  subroutine with the given registers until it returns, under the same checks (the test of
  `FloatToInt` on 33 values uses it).

`--asm` implies `--standalone`. `test_engine.py --asm` runs the groups shared with the Axe
engines that the port covers so far: `parameter_errors()` (rejected and missing input) and
`check_calls()` (the check call, bad characters, B, ʟBIN's check, and the auto-mode draw
calls that fail before drawing). Plus the port's own: `asm_parameters()` (GV's conversion,
archived variables, the speed), `asm_characters()` (`CH` on 531 tokens and `AV` on all
256 bytes, called directly and compared with qrtest's tables) and `asm_codewords()` (the
data codewords in L₁ after a draw call, compared byte for byte with
`qrtest.data_codewords`, which builds them from the `qrcode` library's own BitBuffer the
way its `util.create_data` does: the sweep's payloads at every version, plus skipping and
clamping; 271 sets in the full run). The other groups join as the milestones reach them;
`asm_codewords()` can go once the sweep runs, since the drawn symbols cover it. `run_all.py` runs `test_z80sim.py` always and `test_engine.py --asm`
when the build has `build/standalone/_theta_QR.8xp`.

## What the engine needs from the OS (first guess, to check)

| Axe engine | Assembly |
| --- | --- |
| `GV`: read an OS real, 0 if missing | done: `_ChkFindSym` with the name in OP1 (type 0, the letter, 0, 0), then our own `FloatToInt` (no `_ConvOP1`, whose range checks would be the OS's) |
| store B (only if it exists) | `_ChkFindSym`, then write the float into its data |
| `→Ans` | done: `_SetXXXXOP2` + `_OP2ToOP1` + `_StoAns` (in `Quit`) |
| Str1, Str2, ʟBIN | Str1 and ʟBIN done: `_ChkFindSym` (Str1 = type 4, AAh, 00h; the list = type 1, 5Dh, "BIN"); DE = the size word |
| notes, archived ones read through `Y₁` | `_ChkFindSym`: B = flash page (0 = RAM); skip the archived entry's header; read bytes with `_LoadCIndPaged` (or map the page, then restore port 6) |
| E=4: list notes into Str3 | walk the VAT; `_DelVarArc` an old Str3, `_CreateStrng` |
| `Full` | detect an 84+/SE (port 2) and set port 20h; the OS goes back to 6 MHz itself (design.md item 16) |
| `Rect(`, `Pxl-On(`, `DispGraph` | own drawing into `plotSScreen` and the reserved-module map in `appBackUpScreen`; display with `_GrBufCpy` (handles LCD timing) |
| L₁, L₃ scratch | the same areas (`saveSScreen` 86ECh, `appBackUpScreen` 9872h) and the same memory map as design.md |

Assembly gotchas to respect: keep IY intact (the OS needs it for bcalls and interrupts),
leave interrupts on, balance the stack, don't touch RAM the OS owns.

## Decisions made while porting

- **Variables** live at saveSScreen+714 (`Vars`), the last 54 bytes of saveSScreen, where Axe
  keeps its own: L₁ stays 714 bytes, as the memory map in design.md assumes, and the
  variables cost no program bytes.
- **Leaving:** `Quit` (Ans = HL) first restores the stack pointer saved at the start
  (`SaveSP`), so any routine can end the program, like Axe's `Return` at the top level.
  `BadInput` is Quit with 65535.
- **Numbers from the OS** (`FloatToInt`): the integer part, the fraction dropped; a negative
  number or one of 65536 or more gives 65535, which every parameter rejects or clamps. Axe's
  `float{` isn't documented for those (axesim refuses them), so this is a choice, not a copy.
  Values above 255 are rejected before they are cut to a byte (V=256 must not read as 0).
- **Archived variables** are treated as missing (a real reads as 0, Str1 or ʟBIN is bad
  input), as the Axe engine's GetCalc does. Notes are the exception (milestone 8).
- **Order:** E is read and E=4 dispatched before V and M are read, as in the Axe engine.
- **Tables** are the Axe engine's (GDB0, GDB1, GDB9 as `TokenFirst`/`TokenSecond`,
  `Prefixes`, `Punct`), generated from QRSRC.axe.txt's hex. `inData(` becomes `cpir`: after
  a match BC = what was left to search, so the 1-based position is the length minus BC
  (`CH`: ASCII = 126 - C; `AV`: value = 44 - C).
- **`AV`** answers with carry (set = no alphanumeric value) instead of Axe's 99.
- **Storing B** writes only a real B in RAM (the type from its VAT entry, at HL after
  `_ChkFindSym`): a complex B is left alone, since a real's float in its first half would
  leave it half real. The float comes from `_SetXXXXOP2`.
- **Jumps:** `jr` reaches only 128 bytes, so the far ones (to `BadInput`, to `Scanned`) are
  `jp`; spasm refuses a `jr` that is too far, so this can't go wrong silently.
- **Bit packing** (`AB`): the value goes in HL, the bit count in B; HL is shifted so the
  first bit is bit 15, then `add hl,hl` / `rla` moves one bit at a time into the byte being
  filled (kept in A while AB runs, in `BitAcc` between calls). An alphanumeric pair's
  45·first is computed as 9·(5·first) with shifts and adds. ʟBIN elements go through
  `FloatToInt`, so one over 65535 (never sent by prgmQR) gives FFh where Axe's `float{`
  would wrap around; up to 65535 both take the low 8 bits.
- **Later:** the test "N far over capacity writes nothing past L1" compares L₁+714 onwards,
  which is where the port keeps its variables (Axe's live in axesim's Python). At milestone 7
  it needs to start after the variables (L₁+768) for the port.
- **Not tested:** 65532 (over 32765 characters) for Str1 or ʟBIN: neither fits in the
  harness's RAM that long. Milestone 8 tests it with an archived note, as for the Axe engine.

## How to port

- Mirror the Axe engine: same subroutines under the same names (`AB` append bits, `CH` next
  character, `AV` alphanumeric value, `RS` Reed-Solomon, `CW` codeword in interleaved order,
  `FP`/`AP` finder and alignment patterns, `MA` note character, `NH`/`NF`/`RB` notes, `GV`, plus
  the E=4 listing), same tables (GDB0-GDB9 become `.db` tables), same memory map. Make it
  bit-for-bit equivalent first; speed it up later.
- Every routine gets a header comment: inputs, outputs, registers changed. Comments cost
  nothing on the calculator (assembled on the PC), so explain freely, in the style of the Axe
  comments (sentence case, the cryptic parts explained).
- Use 8-bit values where they fit, and tables over loops where cheap: that's where the size and
  speed come from.

Milestones, each with the tests that cover it:

1. Tools and harness, with a tiny program (`Full`, Ans = 0) through the harness, then on the
   calculator (safe, and it proves the program format and the Ans handling). Done, and run on
   the user's calculator: Ans = 0, no crash (prgmQR then draws nothing, as expected). The port
   keeps the engine's name all along (the user's choice): sending it replaces the working
   prgmθQR, and compiling QRSRC in Axe again brings that back.
2. Reading parameters (`GV`) and the error answers: the "rejected" and "missing variable"
   tests. Done, and checked on the calculator.
3. The check call (V=0) for Str1: lengths, auto/ASCII/alphanumeric, bad characters and B.
   Done, and checked on the calculator.
4. Bit packing into the data codewords: compare memory with a Python reference before
   going on. Done in the harness.
5. GF(256) tables, the generator polynomial, `RS`.
6. Drawing: function patterns, format and version information, the zigzag through `CW`. Now
   the sweep's symbols can match.
7. ʟBIN, skipping (O), clamping N.
8. Notes: RAM, archived, the character swaps, the non-ASCII warning.
9. E=4: the note list in Str3.
10. Full test pass, then size and speed against the Axe engine, then the calculator.

## On the calculator

- Back up the calculator with TI Connect first: an assembly bug can clear RAM.
- Try milestone 1 alone, then the full engine with the standalone prgmQR.
- The things only hardware will show: archived notes, creating Str3, `Full` on an 83+ vs an
  84+, the display.

## Repo layout (proposal)

- `src/standalone/_theta_QR.z80`: the source (file names spell θ as `_theta_`, as TI Connect needs).
- `build.py` assembles it (when spasm-ng is found) to `build/standalone/_theta_QR.8xp`.
- `tools/z80sim.py`: the harness; `--asm` in the standalone engine and note tests.
- When it works: `docs/standalone/readme.txt` and `API.md` say to send `_theta_QR.8xp`
  instead of compiling QRSRC; a design.md item records the port.

## Questions for the user

- Once it works, replace the Axe engine in the standalone release, or ship both?
- How much commenting do you want, given you'd read it less easily than Axe?
