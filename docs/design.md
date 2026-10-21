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
6. The negative-sign token (B0h) was treated as minus (71h) in both text modes (undone in item 44).
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
19. A public interface for other programs (`docs/legacy/API.md` now; the release's is `docs/API.md`): every OS variable is read through
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
25. QRBASIC versions 5 and 9: drawn when set explicitly (a set version means that size, as in
   the hybrid); the automatic pick still bumps 5→6 and 9→10, which stay a little faster even
   with the XOR table (more XORs per byte in 5 and 9 outweigh the smaller drawing). Their
   generator tables are back (from git, as before).
   Then the user timed every version: with the XOR table, 5 is faster than 6, so the automatic
   pick skips 5 only with the table off (`V+(V=9 or V=5 and not(ʟQROPT(4→V`); 9 is always
   bumped to 10.
26. QRBASIC drawing: row flags. TI-BASIC's and/or never short-circuit, so the zigzag paid
   for the whole r₁ test (fixed-pattern module?) on every module; at v7+ that test is long.
   Each version branch now also builds L₃ (free by then: the EC tail is already in ʟCW) by
   `seq(…,N,0,S-1`: 1 for rows where r₁ can be true (v1: row 6; v2-6: 6 and the alignment
   band; v7+: rows 0-6 and the alignment bands), and the zigzag runs
   `0 : If L₃(I+1 : r₁ : If not(Ans` (If leaves Ans alone, so unflagged rows skip r₁).
   In tibasic, r₁ evaluations at v11 went 3434 → 958; v1 does ~5% more work (its r₁ was
   just I=6).
27. QRBASIC Redraw (main menu, Lbl R): draws whatever ʟCW holds, for timing the drawing alone.
   V comes from dim(ʟCW) (all codewords plus the final 0: 27, 45, 71, …, 405) via
   `int(.2dim(ʟCW)^.68` (exact at all 11 lengths, ≥0.12 from the next integer; found by a
   search, like the original QRDRAW's `int(√(8n+400)/4-4-(27≥n`); startTmr, then `Goto D` (Lbl D just before FnOff). T is then
   the drawing time. The menu text is "R\edraw": in max mode "Redraw" tokenized as the
   TI-84+CE color token Red (EF42) + "raw". build.py now refuses a BASIC program whose
   tokens need more than a monochrome TI-83+/84+ (`get_min_os()`, MONOCHROME).
28. The note picker became its own Axe program, prgmθNOTES (`src/legacy/NOTESSRC.axe.txt` now), for an
   encryption add-on that will also open notes (design notes, not in the repo:
   https://claude.ai/code/artifact/d8acc6c5-46a9-4ad8-8d6d-6c8d7911a7e0). It is the `filepicker`
   branch's menu (item 12), returning just the name: Ans 1 picked, 0 cancelled, 2 no notes.
   prgmθQR lost E=4 (`LS`, `NC`) and prgmQR lost the 5-at-a-time Menu( pager. The name moved
   from Str3 to Str2 (free once the pager's name list was gone): Str1 stays the user's typed
   text only (so 2nd RCL Str1 still brings a message back), Str2 is the note name. RAM:
   `Asm(` needs room for the running program only, so a separate picker adds its stored size
   but not to the peak. Still duplicated in both programs: `NH` and `RB` (is it a note, read
   a byte) and the GDB8 signature.
29. The QR-only release (no encryption) lived in `src/standalone/` on master, so it could be
   built and tested without switching branches: the previous prgmQR and engine (commit
   14b59a2, branch `basic_notefolio`; the user likes its BASIC pager) with one change, the
   list of names (E=4) now in Str3 and the chosen name in Str2, matching the main set's Str2.
   Same program names, built to `build/standalone/`. A fix that applied to both engines had
   to be made in both copies (see item 47 for what became of the two sets).
30. TI-83+ copy of QRBASIC: the stopwatch (`startTmr`, `checkTmr(`) is the only thing in either
   release that needs a TI-84+ (checked token by token against tivars' table; the hybrid needs
   TI-83+ OS 1.03, QRBASIC's ASCII table OS 1.15 for its punctuation tokens such as # $ % & @ ~). build.py writes
   `build/83_safe_QRBASIC.8xp`: the source with every timer line removed (`strip_timer`, which
   refuses a timer line right after a one-line If), same program name, so one release ships
   both files and the user sends one. Everything else (θQRBIT, the lists) is shared.
31. QRBASIC stopwatch in three laps, in L₆ (was the total in T): L₆ = {codewords, ECC +
   interleaving, drawing}, whole seconds. L₆ was unused, and QRBASIC already overwrites L₁-L₅,
   so no custom list; three reals (G, H, θ were free) would be harder to find, while L₆ shows
   in STAT Edit. The timer restarts at each boundary (`{checkTmr(A→L₆`, `startTmr→A`, then
   `checkTmr(A→L₆(2`, …), so the laps add up to the total. Redraw: `{0,0→L₆:startTmr→A`,
   giving {0,0,drawing}. Every timer line (and that whole Redraw line) is cut from
   83_safe_QRBASIC, which leaves L₆ alone.
32. Stopwatch removed: it was for testing, and the release is one QRBASIC for every model (the
   83_safe copy became QRBASIC; no `strip_timer`, no 83_safe file). The three-lap version is
   kept on branch `timer3`. build.py now refuses any BASIC token a TI-83+ lacks (was: any a
   monochrome TI-84+ lacks), so a timer command can't come back unnoticed. L₆ is unused again.
   Redraw (item 27) stays: it still redraws ʟCW, just untimed.
33. Engine size (standalone prgmθQR: 6423 bytes compiled, MirageOS build disassembled in
   `build/dump/`): main body 51%, subroutines 37% (NoteFolio ~930 bytes: LS, NF, NH, NC, RB,
   MA), Axe's library 6%, data 6%; drawing about a third. So the drawing went to Axe's
   rectangle commands: finder and alignment patterns and the reserved-module map (`RV`, a
   Pxl-On loop, removed) are `Rect(`/`RectI(` calls, faster too. `CW`'s M/B and B-(M^B),
   recomputed per codeword, are now set once before the zigzag (T and U). Both engines.
   Result: standalone prgmθQR 6423 → 6267 bytes (156 saved; Axe adds its rectangle routines).
34. A removed; auto mode's decision travels in M. A was only read by draw calls in auto
   mode (the check's answer, copied back by prgmQR), so a missing or leftover A gave a code in
   the wrong mode, silently (a leftover 1 with non-alnum text scanned as the wrong text). Now
   the check stores 1 or 2 in M itself (only if M exists, like B), and a draw with M=0 (no
   check) runs the same scan, stores M, and draws; it also catches a bad character. Codes are
   unchanged (M=1/2 encode like A=0/1). prgmQR keeps the menu setting in D and copies it into
   M before each check, so the setting survives; ʟBIN sets M=1 for the byte capacity table.
   Per-piece decisions (each split code picking its own mode) were discussed and not done.
   Both engines and both prgmQRs.
35. The check returns just the length (was 2·length+1 if alphanumeric): the mode is in M
   since item 34, so the bit was redundant, and dropping it doubles the limit to 32767
   characters (103 version 11 codes; lengths stay below the 32768+k error codes). M must be
   set before calling (in auto mode it's the only place the choice is reported; the engine
   doesn't create M). prgmQR takes the length straight from Ans; ERR:TOO LONG says 32767.
   Tests: the 32 KB archived note needs the simulator's archive moved to address 0 (its
   default 4000h-7FFFh holds 16 KB).
37. The mode bit went back into the check's Ans (2·length+1 if alphanumeric), and the bad
   character's position moved out of it into B: the usual answer is all in Ans, and the
   exception's details are in a variable. B already held a note's first non-ASCII position, so
   it is now "the first problem character" either way, and Ans says which (65533 error, or a
   normal result with B≠0, a warning). Codes: 65533 bad character, 65532 too long, 65535 bad
   input, 65534 prgmQR's "didn't run". Lengths ≤ 32765 so 2·length+1 ≤ 65531. M is still
   written in auto mode (the draw calls use it), so the bit in Ans is for sizing.
38. ...and the engine stopped writing M (it was redundant with the bit, and an engine that
   changes its inputs is surprising): it writes only Ans, B, and Str3 for E=4. prgmQR sets M
   itself after the check (`If not(M:1+K-2L→M`); D still keeps the menu setting. A draw with
   M=0 still decides by reading the text, but each such call reads it again.
36. QRBASIC cleans up its scratch variables: `ClrList L₁,L₂,L₄,L₅` right after the ECC
   (before interleaving, whose `seq(` builds a second copy of ʟCW, the peak; L₃ still holds
   the EC tail), and at the end `ClrList L₁,L₂,L₃,L₄,L₅` (L₃ = the row flags, up to 61
   elements) and `DelVar Str2`. ClrList keeps L1-L5 defined for the STAT editor. Kept:
   ʟCW (up to ~3.6 KB; Redraw needs it), Str3 (ASCII fix), ʟQROPT, the GF lists.
39. Tried and reverted: QRBASIC with the XOR table kept the remainder split into 4-bit halves
   (high in L₁, low in L₅, with ʟGFX's halves in two more lists, ʟGFXH/ʟGFXL), so the inner
   loop never split or joined bytes. In tibasic a v11 run interpreted 31% fewer tokens, but on
   the calculator it took the same time and needed 4.6 KB more for the lists: the named-list
   reads (4 per element either way) dominate the ECC time.
40. QRBASIC, XOR table off: both XORs (feedback →F, and the remainder update) use logical
   `xor` on bit lists, `.5sum(L₅*(int(2fPart(A/L₅)) xor int(2fPart(B/L₅`, instead of
   QRECC's complex trick `.5sum(L₅*(1=abs(int(2fPart((A+B𝑖)/L₅`. The user's prgmXORTEST
   (`src/XORTEST.basic.txt`: one method, N trials of one random pair, whole seconds) timed
   abs 14 s, xor 11 s, table 4 s: the complex division, complex int(/fPart( and abs('s square
   root cost more than a second real division and xor. 3 bytes bigger. Exact: A/2^k is a short
   decimal, so the bits are exactly 0 or 1.
41. The XOR table option is on by default (ʟQROPT starts as {0,0,0,1}; the user's change), so
   the tests' sweep covers the table and `xor_table()` the logical xor (table off). QRBASIC
   times the ECC again: `startTmr→θ` before the block loop, `checkTmr(θ→θ` after it, so θ
   is the ECC seconds (interleaving and drawing not included). θ was free (θQRBIT doesn't use
   it). This makes QRBASIC TI-84+ only until the two lines go.

42. CodeChat prototype (`src/CHATSRC.axe.txt` → prgmCODECHAT, an assembly program for testing;
   the design outline is https://claude.ai/code/artifact/e83e8ff0-6022-4cb1-bc10-3243f1360518).
   Menu: Send, Receive, New key (a stub: keys come from `tools/codechat.py`), Quit. No QR yet:
   Send writes the digits to note CCOUT, which prgmQR can draw. See the CodeChat section.
43. Axe comments stripped at build time: `build.py` (`strip_axe_comments`) drops every comment
   line except line 1 (the `.NAME` header, which names Axe's output) and every blank line, so
   comments no longer cost RAM on the calculator, and the sources' comments were rewritten in
   sentence case with more explanation of the cryptic parts. Comments are whole lines only (as
   axesim already assumed); `...` blocks are refused. Token bytes: QRSRC 6409 → 3931, standalone
   QRSRC 6839 → 4270, NOTESSRC 2506 → 1228, CHATSRC 9819 → 6921, LOREMSRC 1619 → 1210, SPEEDSRC
   975 → 385, UNPROSRC 590 → 307. Compiled programs are unchanged (Axe ignores comments).
44. The negative sign is a bad character again, in both engines: the Str1 token ⁻ (B0h) no
   longer becomes minus (71h), and a note's negative character (1Ah) no longer becomes `-`
   (it goes out as 1Ah with the non-ASCII warning in byte mode, and fails in alphanumeric
   mode). The user's readme says only the minus sign is valid ASCII. The hyphen (D2h) still
   becomes `-`. CodeChat (CHATSRC) refuses ⁻ too (BAD CHARACTER).
45. ElseIf: Axe's `ElseIf`/`Else!If` (Else followed by If on the same line) replaced every If
   block that was an Else's whole body (`Else` / `If c` / ... / `End` / `End`): 8 in CodeChat
   (the main menu became one chain), 1 in the note picker; the engines had none (their two
   Else+If spots have more code after the inner If). axesim learned the clauses
   (`next_clause`, `next_branch`).
46. From the Axe command list: `ReturnIf`/`Return!If` replaced every `If c` / `Return` /
   `End` (23: 6 in each engine, 8 in CodeChat, 3 in the note picker; a conditional `ret`, 3
   bytes instead of 6), `Fill(PTR,SIZE,0)` every loop storing zeros (the generator and the RS
   remainder in both engines, 4 in CodeChat, the picker's name slot), and `e^(Z-1)` the
   doubling loop that made AB's first mask (both engines, CodeChat; Z is always 1-16 there).
   Token bytes: QRSRC 3914 → 3863, standalone 4253 → 4202, CHATSRC 6827 → 6748, NOTESSRC
   1225 → 1206. Considered and not done: `EndIf` (no loop needs it, no Goto), `P++` (same
   size and speed as `P+1→P` per the command list), `c?a,b` (one spot, reads worse),
   `length(` for a note's end (can't read archived notes; the scan is bounded on purpose).
   Still open: `getKeyʳ` in the note picker (auto power-down), `#ExprOff` (size).

47. Repo layout: the QR-only release moved out of `src/standalone/` into `src/` (and `docs/`,
   `build/`, `tests/`: `test_engine.py`, `test_notefolio.py`, `test_frontend.py`), and the older
   set (the engine with no note list, the separate prgmθNOTES picker, and its prgmQR) moved to
   `src/legacy/` (`docs/legacy/API.md`, `build/legacy/`, `test_legacy_notefolio.py`,
   `test_legacy_frontend.py`, `test_engine.py --legacy`). Reasons: the legacy set was the
   release's duplicate (every engine fix had to be made twice, item 29), and its one extra,
   the picker meant for an encryption add-on, isn't needed: CodeChat writes its output to the
   note CCOUT, which the release's prgmQR lists and draws like any note. The legacy set stays
   built and tested so it keeps working, but gets no fixes. The tag `before-restructure` is the
   repo before the move. The text of the sections below the history still refers to the legacy
   set where it says prgmθNOTES, E=1-3 only or "main set".

48. ʟBIN input removed from the release (prgmQR's Binary entry, the engine's E=2, in both the
   Axe engine and the Z80 port): the release is meant to be useful, and nobody was expected to
   build a list of bytes by hand; the pure-BASIC set keeps Binary as a proof of concept. E was
   renumbered so there's no hole: 1 Str1, 2 a note (was 3), 3 the list of notes (was 4); E=0
   and E≥4 are bad input. Byte mode is still reached by text (ASCII mode, notes). The legacy
   set keeps ʟBIN and its old numbers (E=2 ʟBIN, 3 a note). Sizes: QRSRC 4202 → 4076 token
   bytes, the Z80 port 3386 → 3289 bytes. The tests read the numbers from qrtest (TEXT, NOTE,
   LIST; BINARY only with --legacy).

Ideas offered but not done: transliterate accents (é → e), spell out multi-character tokens
(`sin(` → "sin("), uppercase lowercase letters in alphanumeric mode, mask selection with penalty
scoring instead of fixed mask 0.

## Engine phases (src/legacy/QRSRC.axe.txt; the release's src/QRSRC.axe.txt adds E=4, the note list)

1. `Full` (15 MHz where supported). Read `E`.
2. Read `V` and `M` (into Axe var F). Reject V>11, E outside 1-3, or M>2 with 65535.
3. Find the input and its length T: list BIN (E=2, forces F=1), the note named in Str2 (E=3,
   `NF`), or Str1 (E=1; T counts tokens).
4. Text, check call or a draw in auto mode (otherwise encoding trusts the check): read every character through `CH` (Str1
   token → ASCII via GDB0, 0 if none; or note character → byte via `MA`) and `AV` (ASCII →
   alphanumeric value, 99 if none). K = first position outside printable ASCII and newline,
   X = first non-alphanumeric. Forced alnum uses X as K; auto becomes alnum if X=0. If K: a
   stores K in OS var B (if B exists); a note in byte mode carries on, anything else returns
   65533. F is now 1 (byte) or 2 (alnum).
5. V=0: return 2T+F-1, or 65532 if T>32765 (checked before the scan, so a length can't be
   mistaken for an error code). Otherwise read `N`, `O` into θ (count to skip).
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
10. Draw. Back buffer = reserved-module map in module coordinates (`Rect(…)ʳ`:
   finders+separators+format areas, timing row/column, alignment 5×5s, version blocks for v≥7).
   Main buffer gets finders (`FP`: 7×7 Rect, 5×5 RectI, 3×3 Rect), timing, alignment (`AP`:
   5×5 Rect, 3×3 RectI, center pixel; each pattern sets its own light modules, so the order
   against the timing pattern doesn't matter), format bits (always 77C4h = EC L,
   mask 0, so the 18 dark modules plus the dark module come from the GDB7 table), version info (v≥7), then data in the standard zigzag, skipping reserved
   modules. Mask 0: a data module is dark iff its bit equals (x+y) mod 2. DispGraph, Ans=0.

## Memory map

| Area | Use |
| --- | --- |
| L₁+0..323 | data codewords |
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
next character → ASCII A, AV ASCII A → alnum value J, RS EC for one block, FP finder, AP alignment, MA calculator char C → output byte A,
NH is it a note (sets Q or opens Y₁), NF open note named in Str2, RB read byte r₁ of the
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
D6h ↔ 0Ah (Enter ↔ the calculator's 0Ah character), F1h → space, D2h (hyphen) → `-`; every other byte goes out unchanged (so in byte mode a scanner shows its Latin-1 meaning).
Anything outside printable ASCII and newline sets B (the warning), never fails.

VAT scan (prgmθNOTES): entries from `progPtr` (word at 9830h) down to `pTemp` (982Eh). Type in the
low 5 bits at P (15h = appvar), name length at P-6, name bytes from P-7 downward, next entry at
P-7-length. Only names made of A-Z, 0-9, θ are listed (others couldn't be opened by name).

## BASIC front end of the release (src/QR.basic.txt)

The legacy front end below, except the NoteFolio entry (Lbl N) and no Binary entry (item
48): it runs the engine with E=3 (`65534` in Ans first, as for every call): Ans = the number of notes K (0 → "No Files"
menu), Str3 = their names, 8 characters each. A `Menu(` shows five names at a time
(`sub(Str3,8P+1,8)` ...) with "More" (P+5) and "Back" (P-5, or the main menu from the first
page); the chosen name goes to Str2 (`sub(Str3,8I-7,8)`), then E=2 and the check flow of Lbl C.
The main menu also has a Mode entry cycling Auto/ASCII/Alnum (D); a Text-mode label rename
there is the user's call (the pure-BASIC set's menu says Text).

## BASIC front end of the legacy set (src/legacy/QR.basic.txt)

Main menu: Message (Lbl M), NoteFolio (N), Binary (ʟBIN) (B), Set version (S),
Mode:Auto/ASCII/Alnum (T; cycles D 0→1→2→0, label via `sub("Auto ASCIIAlnum",5D+1,5`), Exit (X).
Text goes through a check call first (Lbl C: M=D, V=0, B=0; in auto the check sets M to 1 or 2,
and D keeps the setting); a bad character goes to Lbl F, a home-screen
error (ERR:BAD CHAR, or ERR:NOT ALNUM when D=2; the character from Str1, and the position),
Pause, then the main menu. A note with non-ASCII characters (B≠0 after the check) shows
NON-ASCII CHARS and the position, Pause, then goes on to encode. Version selection and splitting live in BASIC (Lbl Q): capacity
table (alnum when M=2 after the check, else byte; ʟBIN sets M=1; EC L) into L₁; C = capacity per code (the set
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
(v11 ends at x=77). (It was at the left edge, x=0, before.) The check call allows 32765 characters (103 version 11 codes), so 3-digit
counts happen at version 11 too (they still fit, from x=83). Longer: ERR:TOO LONG (Lbl G), Pause, main menu.
Keys (Lbl K): Enter/→ next, ← back, Clear stops; ← on the first and → on the last do nothing;
Enter on the last ends. NoteFolio (Lbl N): `Asm(prgmθNOTES`; Ans=1 → E=3 and the check and
version flow from Lbl C; anything else → main menu (65534/65535 → the Asm error menu). Scratch:
U requested version, D mode setting, M mode for the engine, L length, B first non-ASCII, K, L₁, Str1, Str2; split: J
codes, C capacity per code, W per code, P current, O skip.

## Note picker (prgmθNOTES, src/legacy/NOTESSRC.axe.txt)

It starts with `Asm(EF7045)` (bcall _RunIndicOff, 4570h): the run indicator, drawn by the OS
interrupt into the LCD's top right corner, showed over the title bar. (Axe's `DiagnosticOff`
would also stop the OS printing "Done" after the calling program.) `LS` walks the VAT (below) and keeps appvars that pass `NC` (name only A-Z, 0-9, θ, copied
to L₁+700 as an OP1 name) and `NH` (signature, size ≥ 27): names at L₁+8k, 0-padded, at
most 80 (L₁+0..639). Selection sort with `LT`; L₁+690..698 is the swap buffer and the
0-terminated name for `Text(`. Small font with `Fix 5` (draw to the buffer; `Fix 4` again
before every return, or the OS keeps drawing text to the buffer). Title "Choose a NoteFolio
file:" (GDB1, ASCII bytes so the lowercase is exact) at (10,0), centered: 75 px of ink in the
small font by tibasic's `fonts.py` widths, centered in x=0-94 with margins of 10 (a test checks this when
../tibasic is present). In an inverted bar (`RectI(0,0,95,7)`: x=0-94, rows 0-6; column 95 is reserved, as in prgmQR; like the OS's menu
titles). A large-font title was considered: 7-row text + 1 px padding each side = 9 rows,
and 9+1+8·7 = 66 > 64, so it would cost a name per column; kept small. Then
columns of 8 names 7 rows apart (two blank rows between names; it was 9 names 6 apart, which
the user found cramped; 9 at 7 don't fit under a title), 2 columns shown: name k (counting
from the left column shown, T·8) at x=(k/8)·48+2, y=(k mod 8)·7+8. The selection S is
inverted with `RectI(` (47×7, from y=(k mod 8)·7+8: small-font glyphs leave their top row of
6 blank, so this puts one blank row above the ink and one below; the last row ends at y=63).
getKey: Up/Down ±1 (continuing into the next column), Left/Right ±8 (Right into a shorter
last column goes to its last name), stopping at the ends; Enter picks, Clear cancels. The
view scrolls a column at a time to keep S visible. No notes → "NO NOTEFOLIO FILES" until a
key, Ans=2. Enter: Str2 = the name without padding (GetCalc("Str2",L)), Ans=1; 65535 if Str2
can't be created.

Leaving (`EX`, every exit): an assembly program returning to the home screen doesn't make
the OS redraw it, so the menu stayed on the LCD with the result printed over it. `EX` clears
the buffer and shows it (blank LCD), then redraws the home screen's text from the OS's copy,
textShadow (8508h, 16×8 character codes): `Output(` + `Disp …►Char` per cell, with `Fix 7`
so the last cell can't scroll the screen (`Fix 6` after), and curRow/curCol (word at 844Bh)
saved and put back so the OS prints the result where it would have. The graph buffer is left
clear (its old contents, e.g. a drawn QR code, are lost, as before).

## CodeChat (src/CHATSRC.axe.txt, tools/codechat.py)

Message = header (4 bytes: 10h + flags [bit 0 compact, bit 1 odd count], key ID, 2-byte
counter big-endian; it was 4 bytes, cut to save 5 digits a message) + AES-SIV tag (16) + ciphertext; the header is S2V's one associated-data string
(RFC 5297; `cryptography`'s `AESSIV(key).encrypt(text, [header])` gives tag + ciphertext).
Key = 32 bytes: K1 (first half) for S2V/CMAC, K2 for CTR. Key ID = byte 0 of AES(K2, 0¹²⁸).
The counter's last bit is the sender's side; it grows (CCSTATE, one counter for all
contacts, +1 or +2 to land on my side's parity), saved and archived before encrypting, and
starts over after 65535: 32,768 messages per side. A repeat only shows that two messages
with the same counter and key have the same text (AES-SIV); 1 byte (128 per side) was
rejected for repeating often enough to match short replies like "YES".
Digits: each 2 bytes → 5 digits (00000-65535), a last odd byte → 3; receiving ignores
non-digits, refuses a group over 65535 or a count that isn't 5k or 5k+3. Compact alphabet
0-9 A-Z then space ? ! ' , - . / : (values 0-44), pairs in 11 bits, odd last in 6, zero pad.
8-bit text = calculator character codes (ASCII but $ = F2h, [ = C1h).

Appvars (OP1 names in GDB7-9): CCKEYS = version 1, count, entries of name 8 + my side 1 +
key 32, may be archived (read through Y₁); CCSTATE = 2-byte counter (an old 4-byte one is read as its high word, so it starts over); CCOUT = a NoteFolio note
of the digits (header from TEST.8xv: the 4 unknown bytes 80 10 62 21, title CCOUT, trailing
00 00 00). The PC script writes keyrings with the archive flag set, as TI Connect files do.

Send: contact (menu if more than one, keys 1-6), `input` → tokens → ASCII via θQR's table
(GDB0/GDB1) into L₃; a token without a character is refused. Compact if every character is
in the alphabet; lowercase only → "uppercase / as typed" with both digit counts; anything
else → 8-bit after a confirmation with the digit count. Limits: 418 compact, 288 8-bit
(one version 11 code). Receive: type digits, or read CCOUT; for each keyring entry whose key
ID matches: my own side → remember (H), other side → CTR, then the tag (`TR`; CTR again to
undo if it fails). "SENT BY YOU" only when no other-side key was tried. Text shows on the
home screen, 112 characters a page (Fix 7, so the last cell doesn't scroll).

Keys: every wait is `WK`, which uses `getKeyʳ` (the OS's blocking _GetKey) rather than a
`getKey` loop: only _GetKey runs the OS's auto power-down (the user's app never turned off on
its menu), 2nd+ON works, and the CPU sleeps between interrupts instead of spinning at 15 MHz.
_GetKey has its own codes (ti83plus.inc k...): `WK` turns 1-6 (8Fh-94h, GDB4+8) and F1-F5
(Y= WINDOW ZOOM TRACE GRAPH: 49h 48h 2Eh 5Ah 44h, GDB4+15) into θ = 1-6, Clear (09h) into
255, anything else into 0. Main menu: 1/F1 send, 2/F2 receive, 3/F3 new key, 4/F4 or Clear
quit; Clear backs out of the contact list and the questions.

Memory: L₁ message from 2 (header 2-5, tag 6-21, text 22-321), key entry 330-370 (name, side 338, K1 339, K2
355), round keys 380-555, CMAC subkeys 576/592, S2V D 608, CMAC out 624, scratch block 640,
CTR counter 656, temp 672; L₁+690 a name for display. L₃ typed characters. Variables:
AE uses W U I J Z r₂-r₆, KX W I J Z, CM P N K O M C I, DB Y C I, CT O K C I; the main code
keeps its values in other letters across them. The main menu is an If/Else chain: θ is
changed inside every choice (a test caught Send's cancel key opening Receive).

Tests: `tests/test_codechat.py` runs the source in axesim with `app=True` (writing into the
program's own data raises, as a Flash app can't): AES (FIPS-197 C.1) and CMAC (RFC 4493, 0/16/
40/64 bytes) by calling the subroutines, sends compared byte for byte with the Python
reference, receives of reference messages, CCOUT round trip, errors, paging.

## Risks: not verified on hardware

- Never compiled by a real Axe. Syntax checked against Axe 1.2.2 Commands.html, the 1.1.2
  Documentation.pdf and the TokenIDE token table.
- ʟBIN found via raw OS name bytes (fallback if it fails: `GetCalc("ʟBIN")`).
- Archived notes read through Axe files (`GetCalc(name,Y₁)`, `{Y₁+k}`, `{Y₁-2}ʳ`).
- VAT entry layout as above.
- The graph-redraw assumption behind `ClrDraw:DispGraph` before `Asm(`.
- CodeChat: compiled size not known; the estimate (~7.5-8 KB) is close to the 8,811 bytes an
  assembly program can run (code past C000h crashes). Check before running; else compile as an app.
  What ON does while `getKeyʳ` waits (some OS routines treat it as break). `input`'s result is assumed to be token data with its size in the 2 bytes before (like an
  OS string); `Archive`/`UnArchive` with an OP1 name pointer; `Output(X,Y,PTR)` near the last
  row is kept under 16 characters so it can't scroll.
- The note picker: `Text(`/`Fix 5`/`RectI(`/`getKey` are modelled loosely in axesim (text is
  recorded, not drawn), so the menu's look and key handling are only checked on hardware.
  The home-screen redraw assumes textShadow holds plain displayable codes (`Disp ►Char` uses
  the OS's character output, which might treat a few codes specially) and that `Fix 7` stops
  the bottom-right cell from scrolling.

## References

- Axe 1.2.2 command list: https://axe.eeems.ca/Commands.html ; guide: https://axe.eeems.ca/Documentation.pdf
- Axe token table: https://github.com/merthsoft/TokenIDE (Tokens/AxeTokens.xml)
- Calculator character set and RAM addresses: `inc/ti83plus.inc` in https://github.com/alberthdev/spasm-ng
- Notefolio layout: https://github.com/UltraAlex00/NoteFolioEdit (Parser.bas)
