# Plan: the engine in Z80 assembly

Status: milestones 1-9 are done in the harness, so the port does everything the Axe engine
does; 1-7 also on the user's calculator (milestone
2 from the home screen: a valid call 0, V=12 and V=256 65535; milestone 3 through prgmQR's
bad-character screen and from the home screen: HELLO 11, A=B 6, forced alphanumeric 65533
with B = 2; milestones 6-7 through prgmQR, drawing codes that scan; all as in
the harness).
`src/_theta_QR.z80` (3409 bytes since the new interface, design.md item 53) does everything the Axe engine does for Str1
and NoteFolio notes (in RAM or archived): the check call and the draw calls
(data codewords, error correction, the drawing, DispGraph, Ans = 0), and the note
list in Str3. Its interface has changed twice since the milestones: ʟBIN was dropped
(design.md item 48: E 1 Str1, 2 a note, 3 the list), then the command became its own
variable (item 53: C 0 check, 1 draw, 2 list; I 0 Str1, 1 a note; V 1-11 only for a draw;
a draw needs M 1 or 2). The plan below still speaks the interface it was written for: ʟBIN,
E=3 for a note and E=4 for the list, V=0 for a check, and 3386 bytes. Every test of `test_engine.py` and `test_notefolio.py` passes
against it (the sweep's 262 symbols, the notes' symbols, the 32 KB archived note, the list).
`NotYet` is gone. Time in the emulator for a full code drawn (OS
calls not counted): version 1 0.04 s, 5 0.15 s, 10 0.32 s, 11 0.38 s at 15 MHz (0.94 s at
6 MHz). A 32,000-character archived note: checking it 1.9 s at 15 MHz (4.75 s at 6 MHz),
drawing 300 of its characters at version 11 0.44 s (1.09 s), with no OS calls while reading
it (it was 2.43 s and 1.06 s plus one `_LoadCIndPaged` per byte read, 64,008 and 32,308; see
"Notes" under the decisions). For comparison, the compiled Axe engine was
6267 bytes (design.md item 33), about 930 of them for the notes.
It is the release's engine now (design.md item 52), and the Axe engine is frozen as
`src/legacy/QRAXE.axe.txt`. `tools/z80sim.py` runs it; `python tests/test_engine.py` and
`python tests/test_notefolio.py` test it (by default; `--axe` tests the Axe engine instead), and `tests/test_z80sim.py` checks
that the harness catches each kind of mistake and models the OS routines as described below.

## Goal

Rewrite the engine, prgmθQR (`src/QRSRC.axe.txt`, now `src/legacy/QRAXE.axe.txt`), as a
hand-written Z80 assembly program with exactly the same interface (`docs/API.md`):
the same program name, the same OS variables in (E, V, M, N, O, Str1, Str2, ʟBIN), the same
answers out (Ans, B, Str3), and the same drawing. prgmQR stays as it is: it
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
loads `build/_theta_QR.8xp`, and an `--asm` switch in `test_engine.py`
and `test_notefolio.py` that picks it. Then the whole existing sweep (versions 1-11,
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
  (port 6 page mapping at 4000h-7FFFh, and `_LoadCIndPaged`, which it used at first).
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
  TI-84+ only (`full`), port 6 (bank A's page) read and written (`bank_a`), any other port
  raises. Bank A must hold the OS's page again (`OS_PAGE`) when the program returns.
- **Variables and the VAT:** `set_real`, `set_str`, `set_list`, `add_appvar` (each with
  `archived=`) put the data in RAM from C000h, or in the archive (below); `add_vat_other`
  adds an entry with no data (a program, a list), as in axesim. `run()` writes the VAT first
  (`build_vat`): the
  symbol table from symTable (FE66h) down, 9-byte entries (type, T2, version, data pointer
  low, high, page, then a 3-byte name, going down), for reals and strings; then the program
  table from (progPtr) down to (pTemp), entries with a length byte and the name, for lists
  (assumed to live there, since their names are up to 6 bytes; test_unprot.py assumes it too),
  and appvars. `vat_entries()` reads it back.
- **Archive:** flash pages of 16 KB (`flash`). An archived variable is an entry written as
  the OS writes it: FCh, the size of the rest (word), a copy of its VAT entry going up (type,
  T2, version, address low, high, page), the name length and the name, then the data. Its VAT
  entry gives the page and the address of the FCh byte, which `_ChkFindSym` returns in B and
  DE. The archive starts at 3FF0h on page 0Bh, so every archived variable crosses into the
  next page. A read of 4000h-7FFFh gives the archive page that port 6 has put in bank A; with
  the OS's page there (no archive on it) it raises, as does a jump there. `_LoadCIndPaged`
  (C = the byte at page B, address HL in 4000h-7FFFh) also works, and raises for a page with
  no archive on it.
- **bcalls:** `_ChkFindSym` walks that VAT in memory (the symbol table by the 3 name bytes, the
  program table by name and kind): carry if missing, else HL = the entry, DE = the data, B =
  the page. `_SetXXXXOP2` (HL → OP2 as a float), `_OP2ToOP1`, `_StoAns` (sets `ans`),
  `_OP1Set0`, `_GrBufCpy` (records the graph buffer in `displays`), `_LoadCIndPaged`,
  `_MemChk` (HL = `free_ram`, 20000 unless a test sets it), `_DelVarArc` (deletes the
  variable whose VAT entry is at HL, RAM or archive; the VAT closes up), `_CreateStrng` (a
  string named in OP1, HL bytes, in RAM: HL = its VAT entry, DE = its size word; raises if
  one of that name exists, as the OS would quietly make a second, or if RAM is short: the
  string, 11 bytes more, out of `free_ram`).
  `calls` lists them in order, `ticks` is the run's T-states.
- **Single routines:** build.py writes the program's labels to `_theta_QR.lab` (spasm's `-L`,
  filtered to the names the source defines), and `call(label, de=..., ...)` runs one
  subroutine with the given registers until it returns, under the same checks (the test of
  `FloatToInt` on 33 values uses it).

The engine tests run the Z80 engine by default (it took `--asm` until design.md item 52). `test_engine.py` runs every group the Axe engines run
(`check_calls()`, `edge_cases()`, `parameter_errors()`, `skipping()`, `sweep()`, each drawn
symbol compared with the `qrcode` library and decoded by zxing-cpp), plus the port's own:
`asm_parameters()` (GV's conversion,
archived variables, the speed), `asm_characters()` (`CH` on 531 tokens and `AV` on all
256 bytes, called directly and compared with qrtest's tables), `asm_codewords()` (the
data codewords in L₁ and the EC codewords at L₁+330 after a draw call, compared byte for
byte with `qrtest.data_codewords`, which builds them from the `qrcode` library's own
BitBuffer the way its `util.create_data` does, and `qrtest.ec_codewords`, which takes them
from create_data's full sequence and undoes the interleaving: the sweep's payloads at every
version, plus skipping and clamping; 271 sets in the full run; the drawn symbols cover the
same ground, but this one says which codeword is wrong) and `asm_tables()` (`GFTables`
called on its own, since the drawing reuses L₃: the exp and log tables, and the generator,
as logs, for every version, against the `qrcode` library's tables and its product of
(x + 2^i)). `run_all.py` runs them, `test_z80sim.py`, and the same suites with `--axe`
for the frozen Axe engine; the notes' suite (`test_notefolio.py`)
runs on the Z80 engine too (its `arch_at`, which moves axesim's 16 KB archive, is ignored: the
harness's flash pages hold a 32 KB note), plus `asm_list()`: an old Str3 replaced (in RAM or
archived), no notes, too little RAM (65535, the old Str3 kept) and just enough, at most 80
notes of 85.

## What the engine needs from the OS (first guess, to check)

| Axe engine | Assembly |
| --- | --- |
| `GV`: read an OS real, 0 if missing | done: `_ChkFindSym` with the name in OP1 (type 0, the letter, 0, 0), then our own `FloatToInt` (no `_ConvOP1`, whose range checks would be the OS's) |
| store B (only if it exists) | `_ChkFindSym`, then write the float into its data |
| `→Ans` | done: `_SetXXXXOP2` + `_OP2ToOP1` + `_StoAns` (in `Quit`) |
| Str1, Str2, ʟBIN | Str1 and ʟBIN done: `_ChkFindSym` (Str1 = type 4, AAh, 00h; the list = type 1, 5Dh, "BIN"); DE = the size word |
| notes, archived ones read through `Y₁` | done: `_ChkFindSym`: B = flash page (0 = RAM); in flash, skip the entry's header (9 bytes, the name length, the name) to the size word; read bytes with the page mapped into bank A through port 6 (`RB`, `NotePtr`, `NoteTextLen`), as Axe does |
| E=4: list notes into Str3 | done: walk the VAT; `_MemChk` first; `_ChkFindSym` + `_DelVarArc` an old Str3, `_CreateStrng` |
| `Full` | detect an 84+/SE (port 2) and set port 20h; the OS goes back to 6 MHz itself (design.md item 16) |
| `Rect(`, `Pxl-On(`, `DispGraph` | done: own drawing into `plotSScreen` and the reserved-module map in `appBackUpScreen`; display with `_GrBufCpy` (handles LCD timing; the harness records the graph buffer there) |
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
  input), as the Axe engine's GetCalc does. Notes are the exception.
- **A complex ʟBIN** (type 0Dh, 18-byte elements) is bad input: `_ChkFindSym` finds a list by
  name whatever its type, so the engine checks that the VAT type is the one the name is for
  (the Axe engine doesn't: it reads the real and imaginary parts as elements, so a complex
  {72,73} encodes as 48h 00h).
- **Notes** (`NF`, `NH`, `RB`, `MA`) as in the Axe engine: the name from Str2 up to a space
  token, an OP1 name at L₁+700, size ≥ 27, the signature, the text from byte 24 to a 00h
  (bounded by the size). Differences: `NF` stops copying the name at a 9th character (the
  Axe engine copies all of Str2 before checking the length, which a long Str2 would carry
  past L₁). An open note is `NotePage` (0 = RAM) and `NoteAddr`; in flash, `NoteAddr` is
  an offset from 4000h, and `NotePtr` turns "byte k" into a page and an address: the sum can
  pass several 16 KB pages (and 16 bits, for a 32 KB note), so the page goes up by its bits
  14 and up and the address keeps bits 0-13.
  Archived bytes were first read through the OS (`_LoadCIndPaged`, a bcall per byte), and
  every draw call measures the whole note first (the clamp needs its length). On the
  calculator that made big archived notes noticeably slower than the Axe engine, whose file
  reading (`{Y₁+k}`) maps the page with port 6 itself, with interrupts on (seen in the
  disassembly in `build/dump/`). So now: `RB` maps the page into bank A for its one read and
  puts the old page back (what `_LoadCIndPaged` does, without the bcall), and the measuring
  is `NoteTextLen`, a `cpir` for a note in RAM and, in flash, a `cpi` loop with the page
  mapped once per 16 KB page, the old page put back at the end (about 53 T-states a byte,
  where `RB` per byte cost about 340 plus the bcall). Measured in the harness on a
  32,000-character archived note: a draw call 1.06 → 0.44 s at 15 MHz, the check 2.43 → 1.90
  s, before counting the 32,308 and 64,008 bcalls the old way also made.
  Considered and not done: measuring a draw call's note only up to θ+N (the clamp gives the
  same θ and N for any longer length). With the faster measuring it would save about 0.05 s
  per code on a 32 KB note at 15 MHz, and the length would no longer be the real one in
  draw calls. Also not done: reading the check's scan sequentially instead of through
  `NotePtr` for each character (about a quarter of the check's time).
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
- **Error correction** follows the Axe engine step by step (same tables, same places). In
  `RS`, a log sum can reach 508, so its carry becomes bit 8 of the index into the doubled
  exp table (`rl h`). The blocks are counted down (blocks left, B to 1), so a block is one of
  the long ones when blocks left ≤ M mod B. M / B is found by subtracting, as B is 1, 2 or 4.
  `RS` keeps its place in `BlockPtr`/`ECPtr` and moves them on, so the block loop only says
  how long each block is.
- **Drawing** keeps the Axe engine's plan: the map of function modules in L₃ (one pixel per
  module, 12 bytes a row like the screen, at module coordinates), the symbol in the graph
  buffer with the centering offsets. `PixelAddr` (column B, row C, buffer DE → byte HL, bit
  A) serves both; `RectOn`/`RectInv` (column B, row C, width D, height E, buffer IX) fill or
  invert pixel by pixel, which is fast enough for the few rectangles drawn. `CW` finds each
  codeword in place as in Axe, with an `and` for "mod blocks" and shifts for "/ blocks"
  (1, 2 or 4 blocks). The timing loop counts 2V+1 modules each way.
- **More variables** than the 54 bytes at L₁+714 hold: the drawing's are at L₁+600
  (`DrawVars`), space the memory map leaves free (notes use L₁+700 up).
- **Names:** a label that matches an equate in ti83plus.inc (`RectMode` did) makes spasm
  warn and build.py stop, so a clash can't silently change a value.
- **Memory test:** "N far over capacity writes nothing past L1" compares from L₁+768 for the
  port (its variables are at L₁+714..767; Axe's live in axesim's Python).
- **The note list** (`ListNotes`, `NC`) walks the VAT as the Axe engine's `LS` does, but
  takes each appvar's data pointer and page from its VAT entry (P-3, P-4, P-5: just what
  `_ChkFindSym` would return) instead of searching for it by name, and `NC` copies the name
  straight into its slot in the list, which only counts if `NH` accepts the note. Making
  Str3: the Axe engine's `GetCalc("Str3",size)` returns 0 when RAM is short; the port asks
  `_MemChk` first and answers 65535 unless the string plus 32 bytes is free (11 for its size
  word and VAT entry, the rest a margin), so the OS never stops with ERR:MEMORY. That check
  comes before deleting the old Str3, so a refusal keeps it (and a large old Str3 doesn't
  count as free space). Since design.md item 51 the names are sorted (`SortNames`: an
  insertion sort through `SortBuf` at L₁+690, with `Cmp8` comparing 8 bytes), and blank
  names (`BlankSlot`, which the VAT walk uses too) are added to the list up to a multiple
  of 5 before the one copy into Str3; L₁+0..671 holds 80 names and 4 blanks.
- **65532** (over 32765 characters) is tested with a 32 KB archived note, as for the Axe
  engine; a Str1 or ʟBIN that long doesn't fit in the harness's RAM.

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
5. GF(256) tables, the generator polynomial, `RS`. Done in the harness.
6. Drawing: function patterns, format and version information, the zigzag through `CW`. Now
   the sweep's symbols can match. Done in the harness: all 262 match and decode.
7. ʟBIN, skipping (O), clamping N. Done with milestone 6 (the code came with milestone 4;
   `skipping()` and `edge_cases()` pass).
8. Notes: RAM, archived, the character swaps, the non-ASCII warning. Done in the harness.
9. E=4: the note list in Str3. Done in the harness.
10. Full test pass, then size and speed against the Axe engine, then the calculator. On the
    user's calculator (2026-10-20): prgmθQR 3393 bytes as assembly against 6155 compiled by
    Axe (the size its memory menu shows), and at least as fast, except on big archived notes
    (a bcall per byte read; reading flash through port 6 since, not yet tried on the
    calculator). Left: the release decision (replace the Axe engine or ship both) and the
    docs that go with it.

## On the calculator

- Back up the calculator with TI Connect first: an assembly bug can clear RAM.
- Try milestone 1 alone, then the full engine with prgmQR.
- The things only hardware will show: archived notes, creating Str3, `Full` on an 83+ vs an
  84+, the display. For archived notes the harness assumes, from the OS documentation as
  remembered rather than checked: `_ChkFindSym` gives an archived variable's FCh byte in DE
  (the address in its VAT entry); the entry header is 9 bytes, then the name length and the
  name; a variable that runs past 7FFFh goes on at 4000h of the next page; the page number
  `_ChkFindSym` gives in B, written to port 6, shows that page at 4000h-7FFFh, and the OS's
  interrupt handler doesn't mind another page there (Axe's file reading relies on both).
  Archived notes worked on the user's calculator through `_LoadCIndPaged` (only slowly), so
  the entry layout holds; the port 6 reading hasn't run there yet. For the note list: `_MemChk` returns the free RAM in HL;
  `_DelVarArc` takes what `_ChkFindSym` returned (and deletes archived variables too);
  `_CreateStrng` takes the name in OP1 and the size in HL and returns the size word's address
  in DE.

## Repo layout (proposal)

- `src/_theta_QR.z80`: the source (file names spell θ as `_theta_`, as TI Connect needs).
- `build.py` assembles it (when spasm-ng is found) to `build/_theta_QR.8xp`.
- `tools/z80sim.py`: the harness; the engine and note tests run the Z80 engine by default
  (`--asm` until design.md item 52).
- When it works: `docs/readme.txt` and `API.md` say to send `_theta_QR.8xp`
  instead of compiling QRSRC; a design.md item records the port.

## Questions for the user

- Once it works, replace the Axe engine in the release, or ship both?
- How much commenting do you want, given you'd read it less easily than Axe?
