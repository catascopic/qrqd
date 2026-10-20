# Plan: the standalone engine in Z80 assembly

Status: milestone 1 is done in the harness and not yet tried on the calculator.
`src/standalone/_theta_QR.z80` is the stub (15 MHz where there is one, Ans = 0, 18 bytes);
`tools/z80sim.py` runs it; `python tests/test_engine.py --asm` tests it, and
`tests/test_z80sim.py` checks that the harness catches each kind of mistake.

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

Built in milestone 1 (`AsmMachine(program, model='84+', max_ticks=1.5e9)`): the code at
userMem; writes allowed only to OP1-OP6, L₁, L₃, the graph buffer, the program, the stack below
the return address (FE70h-FFDDh; the address itself sits at FFDEh) and the data of variables a
test created; ROM filled with FFh (rst 38h) and a breakpoint at 0038h, so a jump into ROM
raises; registers start at 5A5Ah, so nothing can rely on a start value; at the end the stack,
IY and interrupts-enabled are checked. Port 2 reads the model (bit 7 set on a TI-84+), port 20h
may be written on a TI-84+ only (`full`), any other port raises. bcalls so far: `_OP1Set0`,
`_StoAns` (sets `ans`); `calls` lists them in order, `ticks` is the run's T-states.
`set_real`/`set_str`/`set_list` put data in RAM at C000h, but nothing finds it yet: the VAT and
`_ChkFindSym` come with milestone 2. `--asm` implies `--standalone`; `test_engine.py --asm`
runs `asm_stub()` only, and the existing groups join as the milestones reach them.
`run_all.py` runs `test_z80sim.py` always and `test_engine.py --asm` when the build has
`build/standalone/_theta_QR.8xp`.

## What the engine needs from the OS (first guess, to check)

| Axe engine | Assembly |
| --- | --- |
| `GV`: read an OS real, 0 if missing | `_ChkFindSym` with the name in OP1 (type 0, the letter); convert the 9-byte float to an integer ourselves (or `_ConvOP1`: check its range) |
| store B (only if it exists) | `_ChkFindSym`, then write the float into its data |
| `→Ans` | e.g. `_SetXXXXOP2` + `_OP2ToOP1` + `_StoAns` (check) |
| Str1, Str2, ʟBIN | `_ChkFindSym` (Str1/Str2 type 4, the list as 5Dh + name) |
| notes, archived ones read through `Y₁` | `_ChkFindSym`: B = flash page (0 = RAM); skip the archived entry's header; read bytes with `_LoadCIndPaged` (or map the page, then restore port 6) |
| E=4: list notes into Str3 | walk the VAT; `_DelVarArc` an old Str3, `_CreateStrng` |
| `Full` | detect an 84+/SE (port 2) and set port 20h; the OS goes back to 6 MHz itself (design.md item 16) |
| `Rect(`, `Pxl-On(`, `DispGraph` | own drawing into `plotSScreen` and the reserved-module map in `appBackUpScreen`; display with `_GrBufCpy` (handles LCD timing) |
| L₁, L₃ scratch | the same areas (`saveSScreen` 86ECh, `appBackUpScreen` 9872h) and the same memory map as design.md |

Assembly gotchas to respect: keep IY intact (the OS needs it for bcalls and interrupts),
leave interrupts on, balance the stack, don't touch RAM the OS owns.

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
   calculator (safe, and it proves the program format and the Ans handling). Done except the
   calculator. The stub has the engine's name, so sending it replaces the working prgmθQR;
   compiling QRSRC in Axe again brings that back.
2. Reading parameters (`GV`) and the error answers: the "rejected" and "missing variable"
   tests.
3. The check call (V=0) for Str1: lengths, auto/ASCII/alphanumeric, bad characters and B.
4. Bit packing into the data codewords: compare memory with a Python reference before
   going on.
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
