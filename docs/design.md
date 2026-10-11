# Design notes

## History (why things are the way they are)

1. The original program (in `originals/`) was pure TI-BASIC: QR (menus), QRCW (codewords),
   QRBIT (bit packing), QRECC (Reed-Solomon using a complex-number XOR trick and lists ʟGFL/ʟGFX),
   QRDRAW (drawing via Pxl-On and an `r₁` expression for function-module tests). It was very slow,
   so it skipped versions 5 and 9 (more EC work per block than 6 and 10).
2. Rewrite: an Axe engine does encoding, ECC, interleaving and drawing; BASIC keeps the menus.
   All versions 1-11 are supported (11 is the largest that fits the 64-pixel screen: 61 modules).
   Fixed along the way: "Abort" in QRCW did `Goto 0`, but labels are per program; odd-length
   alphanumeric input used the untruncated string's last character.
3. Notefolio mode added (E=3/4/5) with a paged picker in BASIC.
4. Token tables moved into the engine. Before, BASIC built Str2 (alphanumeric) and Str3 (ASCII),
   and since a program string can't contain `"`, π stood in for the quote, with an "ASCII fix"
   option to supply a custom Str3. Now a real `"` (typed at the Input prompt) encodes as 34,
   π is just unsupported, and ASCII fix plus Str2/Str3 are gone.
5. "Alt punct" removed after discussion with the user: it relabeled alphanumeric punctuation
   (typing `?` stored `$`), so scanned text differed from what was typed. Unsupported characters
   in alphanumeric mode now become `*` (was `$`, which only made sense under alt punct).
6. The negative-sign token (B0h) is treated as minus (71h) in both text modes.
7. Options menu removed (ʟQR list no longer used). Center and StorePic made sense when drawing
   took minutes; now centering is always on and StorePic is left to the user. Safe mode is
   always on; its warning gained "Use ASCII" for alphanumeric input. The engine still takes C
   and S, so this needed no recompile.
8. Main menu reordered: ASCII, Notefolio, Alphanumeric, Binary.
9. The pure-BASIC generator was cleaned up separately (then in `src/basic/`; `originals/` untouched).
   QRCW's three hard-coded ECC/interleave branches became one loop over blocks: Z blocks,
   short length Q=int(M/Z), the last Y=M-ZQ blocks one byte longer (only v10). Each block's
   EC goes straight to its interleaved slot in L₄ = [long blocks' extra bytes][EC][0]; data is
   interleaved with one `seq(` lookup per byte, then L₄ is appended with a loop (not
   `augment(`, which copies the whole list). QRECC was then called once, so it was inlined:
   4 programs. Generator tables are stored as log+1, so `ʟGFL(F)+L₂` and `Ans-255(Ans>255`
   give every ʟGFX index for a codeword in two list ops. Also: `min({a,b` → `min(a,b`;
   "Abort" in QRCW now `Stop`s (was Goto 0 → ERR:LABEL); odd-length alphanumeric uses the
   truncated count. Versions 5 and 9 are still skipped (one line), though the code handles them.
   Not tried: XOR across the whole remainder in 8 bit passes instead of R element passes.
10. The engine's centering input C was removed (always centered).
11. Encoding modes reworked with the user: auto (alphanumeric when every character allows it)
   is the default, with a main-menu toggle Auto/ASCII/Alnum for testing; it applies to messages
   and notes, not ʟBIN. A bad character now always fails with its position (and the character,
   for Str1); no substitution, so safe mode (S), the Continue/Use ASCII menus and the `?`/`*`
   replacements are gone. Reasoning: bad characters should be rare, and 2nd RCL Str1 at the
   msg= prompt brings the message back to fix. The engine got a check-only call (V=0) so BASIC
   can pick the version for the chosen mode. `$` in notes (F2h) now encodes.
12. Memory: `Asm(` copies the whole engine to userMem to run it, so it needs free RAM equal to
   its size on top of the stored copy (archived programs can't be run by `Asm(`). The user hit
   ERR:MEMORY with 7000 bytes free. So the 406-byte interleave buffer (Buff(406), stored inside
   the program) was replaced by reading codewords in place. An engine-side NoteFolio picker
   was built (kept on the `filepicker` branch) but left out for its size; BASIC menus run in
   place and cost no extra RAM.
13. Split messages: independent codes (each a normal QR code, read by any scanner) rather than
   Structured Append (the spec's linked codes, which most phone scanners ignore). The engine
   only gained O, a count to skip; BASIC does the rest. Then the "msg too long" menu (Resize /
   Truncate / Abort) was dropped: everything that doesn't fit is split, and a set version
   splits at that version. Even pieces vs. filling version 11 first: same number of codes;
   even was kept so every code is the same size (one line to switch, see the BASIC section).
14. Encoding calls stopped rescanning the whole text: only the check call (V=0) looks for bad
   characters and decides auto mode; prgmQR passes that decision back in A, and skipping to a
   piece steps over Str1 tokens by length (GDB1) without looking them up, or sets a note's
   position directly. So each code costs about the same however long the message is.
15. The engine was renamed prgmθQR (θ marks helper programs, and sorts after Z); it was
   prgmQRENGINE.
16. The engine starts with `Full` (15 MHz on the 84+ and Silver Editions, nothing on a plain
   83+). The user's TI-84 Plus test (prgmSPEED, `src/SPEEDSRC.axe.txt`) showed the OS
   goes back to 6 MHz when an assembly program ends, so there is no `Normal` before returning.
17. Notes no longer fail on non-ASCII characters in byte mode (a real note, XLIB, had two λ
   where a PC converter meant `]`). Each calculator character goes out as its own code, so a
   scanner shows Latin-1 look-alikes (λ C2h → Â) that a reader can tell are wrong and could
   map back; a `?` replacement would look like a real `?`. The calculator's swaps are undone so
   nothing poses as ASCII: θ ↔ `[`, ⁴ ↔ `$`, its 0Ah ↔ Enter. The check stores the first
   non-ASCII position in B, and prgmQR shows a warning, Pause (ON quits), then encodes.
   Alphanumeric mode and messages (Str1) still fail.
18. Cheap speedups kept only where the code got no bigger or harder to read: the ASCII table
   became two byte rows searched with `inData(` (was a 95-step Axe loop per token: a message
   check is ~10× faster), and the check stops testing alphanumeric after the first failure.
   Not done: reading a note's length from its header (word at +16 = length+24) instead of
   scanning for the 00h; NoteFolioEdit itself scans, and a third header word that is
   documented as the same length isn't, in a real note (XLIB), so the header wasn't trusted.
19. A public interface for other programs (`docs/API.md`): every OS variable is read through
   `GV`, so a missing one is 0 instead of a read from address 0 (a caller can leave out O
   and A). Version picking stays in the caller (prgmQR's tables, copied into the doc).
20. The pure-BASIC set became prgmQRBASIC + prgmθQRBIT (θQRBIT is called once per value from
   loops, so it stays separate; QRCW and QRDRAW ran once each and were inlined, about 460
   bytes smaller). Applied from the hybrid: a bad character fails before any work (ERR:BAD
   CHAR, the character, Pos=; a loop that ends itself by setting X=N, never a Goto out of it),
   so safe mode and the `$`/`?` substitutions are gone; too long just truncates, at the set
   version too, with "X of Y chars/bytes encoded" on the Encoding screen (rows 7-8, no
   Pause); the Resize/Continue/Abort menu is gone. Drawn at the top left (no centering
   option, no G/H in any Pxl-On). Options left in ʟQR: StorePic 1, Alt punct, ASCII fix.
   No auto mode (the menu picks Alphanumeric or ASCII); `⁻` stays a bad character; versions
   5 and 9 are still skipped (slower than 6 and 10: 108·26 vs 2·68·18 RS steps) and their
   generator tables were deleted. The ASCII table is copied into Str2 so one check loop and
   lookup serve both text modes. Known: with ASCII fix on and no Str3, `length(Str3` is
   ERR:UNDEFINED (BASIC can't test whether a variable exists).
21. QRBASIC stopwatch: `startTmr→A` right after the input, `checkTmr(A→T` right after the
   drawing (before StorePic), whole seconds, nothing shown; TI-84+ only (the timer tokens
   don't exist on a plain 83+). A holds the start because T is busy until the end (θQRBIT's
   bit count, the r₁ alignment test). Variables in use: Str1 input, Str2 working table, Str3
   ASCII table; L₁ capacities → RS remainder → alignment rows, L₂ generator → alignment
   columns, L₃ powers of 2, L₄ EC tail, L₅ ʟGFX indices → generator terms (L₆ unused); free reals G, H, θ.
22. QRBASIC XOR: three methods were tried, timed by the user (v1, 45 alphanumeric chars, T in
   seconds, drawing ~13 of it): Each, the original bitwise complex XOR per element (QRECC's
   trick) 45; Pass, the same over the whole list in 8 bit passes 45; nibble table 33. Pass
   was dropped (same arithmetic as Each, ~300 bytes bigger). The table is an option
   ("XOR table", ʟQROPT(4), default off) because ʟXOR takes ~2.3 KB: ʟXOR (256 entries,
   16a+b+1 = a xor b) is assumed present like ʟGFL/ʟGFX when it's on; the build writes
   build/XOR.8xl to send once. On: the feedback XOR (→F) and the remainder update (one
   `seq(` over J, ʟGFX(L₄(J)) inline) use ʟXOR. Off: both use the bit trick with the powers
   of 2 in L₅ (last, so with the table on L₁-L₄ are used with no gap). Lists: L₁ capacities →
   RS remainder → alignment rows, L₂ generator → alignment columns, L₃ EC tail, L₄ ʟGFX
   indices, L₅ powers of 2 (table off only).
23. QRBASIC setup: only `SetUpEditor QROPT` (ʟQR renamed ʟQROPT so it doesn't look like code
   data). ʟCW is created by `{32→CW` / `{64→CW` before any read; a missing ʟBIN is
   ERR:UNDEFINED, as in the hybrid. A bare `SetUpEditor` right after restores the STAT list
   editor to L1-L6 (SetUpEditor also sets the editor's columns).
24. The pure-BASIC sources moved from src/basic/ to src/, and their output from build/basic/ to
   build/, next to the hybrid's (the names no longer collide: QRBASIC vs QR). A temporary
   stopwatch split (G after the codewords, H after the ECC, θ after interleaving) settled an
   odd v11 result (table slower than the bit trick): measured properly, v11 ECC took 459 s
   with the table and 1087 s with the bit trick (2.4x, like v1); codewords ~15 s and
   interleaving ~10 s either way. The earlier runs' settings must have differed. Split removed.
: transliterate accents (é → e), spell out multi-character tokens
(`sin(` → "sin("), uppercase lowercase letters in alphanumeric mode, mask selection with penalty
scoring instead of fixed mask 0.

## Engine phases (src/QRSRC.axe.txt)

1. `Full` (15 MHz where supported). Read `E`. E=4 → `LS` (list) and return.
2. Read `V` and `M` (into Axe var F). Reject V>11, E outside 1-3, or M>2 with 65535.
3. Find the input and its length T: list BIN (E=2, forces F=1), the note named in Str3 (E=3,
   `NF`), or Str1 (E=1; T counts tokens).
4. Text, check call only (encoding trusts it): read every character through `CH` (Str1
   token → ASCII via GDB0, 0 if none; or note character → byte via `MA`) and `AV` (ASCII →
   alphanumeric value, 99 if none). K = first position outside printable ASCII and newline,
   X = first non-alphanumeric. Forced alnum uses X as K; auto becomes alnum if X=0. If K: a
   note in byte mode stores K in OS var B (if B exists) and carries on; otherwise return
   32768+K. F is now 1 (byte) or 2 (alnum).
5. V=0: return 2T+F-1, or 65532 if T>16383 (checked before the scan, so 2T+1 and
   32768+position always fit in Ans). Otherwise read `N`, `O` into θ (count to skip),
   and for auto mode `A` (F=A+1: the check's decision, from prgmQR).
6. Size `S=4V+17`; offsets `G=31-S/2`, `H=47-S/2` (always centered). Look up M (data
   codewords), R (EC per block), B (blocks). Clamp N to T, and to 468 (only so a bad
   N can't write past L₁: keeping N within the version's capacity is prgmQR's job).
7. Skip θ list elements (P+9θ), Str1 tokens (by length via GDB1, no lookup) or note
   characters (O=θ). Bit-pack
   into L₁ via `AB`: mode indicator, count (alnum 9/11 bits, byte 8/16 bits for v<10/≥10),
   data (alnum pairs 11 bits, odd last 6 bits; bytes 8 bits; text re-read through `CH`),
   terminator ≤4 zero bits, byte align, pad bytes EC/11.
8. GF(256) tables (poly 11Dh) in L₃: exp doubled at L₃+0..509, log at L₃+512..767. Generator
   polynomial built and converted to logs (all coefficients nonzero for n ≤ 30). `RS` does the
   LFSR division per block. Blocks: short length M/B; the last M mod B blocks get one extra byte.
9. No interleave buffer: the zigzag asks `CW` for codeword Q in interleaved order, which finds
   it in place: data byte Q/B of block Q mod B, then the long blocks' last bytes, then EC byte
   of each block in turn at L₁+330, then 0 (remainder bits).
10. Draw. Back buffer = reserved-module map in module coordinates (rectangles via `RV`:
   finders+separators+format areas, timing row/column, alignment 5×5s, version blocks for v≥7).
   Main buffer gets finders (`FP`), timing, alignment (`AP`), format bits (always 77C4h = EC L,
   mask 0, so the 18 dark modules plus the dark module come from the GDB7 table), version info (v≥7), then data in the standard zigzag, skipping reserved
   modules. Mask 0: a data module is dark iff its bit equals (x+y) mod 2. DispGraph, Ans=0.

## Memory map

| Area | Use |
| --- | --- |
| L₁+0..323 | data codewords; in list mode, collected names (8 bytes each, ≤80) |
| L₁+330..409 | EC codewords (blocks × EC per block) |
| L₁+420.. | generator polynomial as logs (≤31 bytes) |
| L₁+460.. | RS remainder (R+1 bytes) |
| L₁+500..502 | alignment centers while drawing |
| L₁+700..709 | OP1-style appvar name: 15h, name, 0 |
| L₃ | GF tables during ECC; then the reserved-module map |
| L₆ | graph buffer (the drawing) |

Static data: GDB1 two-byte token prefixes (5C 5D 5E 60 61 62 63 7E AA BB EF, for inData);
GDB2 OS name of ʟBIN; GDB3 data codewords per version (words); GDB4 EC per block; GDB5 block
counts, then count-field widths at +11 (byte v1-9, v10+, alnum v1-9, v10+: 8 16 9 11); GDB6 version info for v7-v11; GDB7 dark format modules (9 x,y pairs near the top left,
then 3 k for (S-k,8) and 7 k for (8,S-k), the last being the dark module); GDB8 Notefolio
signature; GDB9 alphanumeric punctuation (space $%*+-./:, values 36-44); GDB9+10/+20 the note character swaps (see Notefolio format); GDB0 the tokens for ASCII 32-126 as two
95-byte rows: first bytes (BBh for the lowercase letters and other two-byte ones, which are all
BB-prefixed), then second bytes (0 for one-byte tokens). `CH` finds a token with one
`inData(byte,row,95)` (position + 31 = ASCII); a second byte of 0 (BB 00 = npv() is never searched.

Variables: E source, V version, N count, F mode (then 1 byte / 2 alnum), S size, G/H offsets,
M/R/B version data, P input pointer (later codeword pointer), T text length, O position of the
character just read, K/X first non-ASCII/non-alnum position while checking, Q the open note
(RAM address, or 0 for an archived note read through Y₁), D/W/K bit writer
pointer/accumulator/bit count, A/Z value and bit count for AB. Subroutines: AB append bits, CH
next character → ASCII A, AV ASCII A → alnum value J, RS EC for one block, RV reserve rectangle
(r₁-r₄), FP finder, AP alignment, MA calculator char C → output byte A, LS list notes, NC copy VAT
name, NH is it a note (sets Q or opens Y₁), NF open note named in Str3, RB read byte r₁ of the
open note, GV OS real named at r₁ → r₁ (0 if missing).

## Notefolio format (NoteFolioEdit's source, confirmed by tests/data/TEST.8xv)

Appvar data (after the 2-byte size word): `F3 47 BF AF`; 4 bytes (nonzero in the real file);
8-byte title (0-terminated if short, may have junk after); word textlen+24; word 18h; word
textlen+24; word 1; text; 00h; 2 more bytes (unknown; `2B 2A` in TEST.8xv). Appvar size =
textlen+27. The engine finds the text length by scanning for the 00h, bounded by the appvar size.

Text uses the calculator's character codes (`ti83plus.inc`, `L...` equates), not tokens:
20h-7Eh match ASCII except 24h (superscript 4) and 5Bh (θ); `[` is C1h, `$` is F2h; accented
letters are 8Ah-B5h, Greek BBh-CAh; D6h is Enter (newline); F1h is a space where a line wrapped.
Engine mapping (`MA`, table at GDB9+10/+20): C1h ↔ 5Bh (`[` ↔ θ), F2h ↔ 24h (`$` ↔ ⁴),
D6h ↔ 0Ah (Enter ↔ the calculator's 0Ah character), F1h → space, D2h/1Ah (hyphen/negative) →
`-`; every other byte goes out unchanged (so in byte mode a scanner shows its Latin-1 meaning).
Anything outside printable ASCII and newline sets B (the warning), never fails.

VAT scan (list mode): entries from `progPtr` (word at 9830h) down to `pTemp` (982Eh). Type in the
low 5 bits at P (15h = appvar), name length at P-6, name bytes from P-7 downward, next entry at
P-7-length. Only names made of A-Z, 0-9, θ are listed (others couldn't be opened by name).

## BASIC front end (src/QR.basic.txt)

Main menu: Message (Lbl M), NoteFolio (N), Binary (ʟBIN) (B), Set version (S),
Mode:Auto/ASCII/Alnum (T; cycles M 0→1→2→0, label via `sub("Auto ASCIIAlnum",5M+1,5`), Exit (X).
Text goes through a check call first (Lbl C: V=0, B=0); a bad character goes to Lbl F, a home-screen
error (ERR:BAD CHAR, or ERR:NOT ALNUM when M=2; the character from Str1, and the position),
Pause, then the main menu. A note with non-ASCII characters (B≠0 after the check) shows
NON-ASCII CHARS and the position, Pause, then goes on to encode. Version selection and splitting live in BASIC (Lbl Q): capacity
table (alnum when the check says so, else byte; EC L) into L₁; C = capacity per code (the set
version's, else version 11's); J = max(1,⌈L/C⌉) codes; W = ⌈L/J⌉ per code (even pieces;
`⁻int(⁻x` rounds up; for full codes first, that line becomes `min(L,C→W`); the version is the
set one, else the smallest that holds W, the same for every code. A message that fits one
code is just J=1. There is no "too long" menu any more: a set version means "codes this
size", so it splits at that version. Lbl H shows code P: O=(P-1)W, N=min(W,L-O), then the
usual encode. After it (Lbl Z, J>1): a fraction at the right edge of the screen, both numbers
right-aligned so ones (and tens) line up: a number starts at x=91-4int(log(n)) (small-font digits
are 4 px, the last being a blank column; column 95 is reserved), so ink ends at x=93. Bar
Pxl-On row 31 under J's digits, x up to 93; Text( rows 24 and 32 (ink rows 25-29 and 33-37,
centered on the bar). Up to 3 digits (from x=83) stay clear of the code's 4-module quiet zone
(v11 ends at x=77). (It was at the left edge, x=0, before.) The check call allows 16383 characters (51 version 11 codes), so 3-digit
counts only happen with a small set version. Longer: ERR:TOO LONG (Lbl G), Pause, main menu.
Keys (Lbl K): Enter/→ next, ← back, Clear stops; ← on the first and → on the last do nothing;
Enter on the last ends. Notefolio picker: E=4 fills Str2, Menu( shows 5 names + More +
Back (More does nothing on the last page; Back goes back a page, or to the main menu
from the first), the pick goes into Str3, then the check and version flow with E=3. Scratch:
U requested version, M mode, L length, A alnum flag, B first non-ASCII, K, P, I, L₁, Str1, Str2, Str3; split: J
codes, C capacity per code, W per code, P current, O skip.

## Risks: not verified on hardware

- Never compiled by a real Axe. Syntax checked against Axe 1.2.2 Commands.html, the 1.1.2
  Documentation.pdf and the TokenIDE token table.
- ʟBIN found via raw OS name bytes (fallback if it fails: `GetCalc("ʟBIN")`).
- Archived notes read through Axe files (`GetCalc(name,Y₁)`, `{Y₁+k}`, `{Y₁-2}ʳ`).
- VAT entry layout as above.
- The graph-redraw assumption behind `ClrDraw:DispGraph` before `Asm(`.

## References

- Axe 1.2.2 command list: https://axe.eeems.ca/Commands.html ; guide: https://axe.eeems.ca/Documentation.pdf
- Axe token table: https://github.com/merthsoft/TokenIDE (Tokens/AxeTokens.xml)
- Calculator character set and RAM addresses: `inc/ti83plus.inc` in https://github.com/alberthdev/spasm-ng
- Notefolio layout: https://github.com/UltraAlex00/NoteFolioEdit (Parser.bas)
