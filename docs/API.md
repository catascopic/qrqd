# Calling prgmθQR from your own program

prgmθQR is the QR engine behind prgmQR. Any TI-BASIC program can use it to draw a QR
code: set a few variables, run `Asm(prgmθQR)`, and read Ans.

**Requirements**
- prgmθQR must be in RAM (unarchived), because `Asm(` can't run archived programs.
- Running it needs free RAM at least the size of prgmθQR: `Asm(` copies the program to run it.

## Quick example

Draws Str1 as one QR code, in the smallest version that holds it:

```
"HELLO WORLD→Str1
1→E:0→M:0→V:0→O
Asm(prgmθQR
Ans→K
If K≥65532:Stop
int(K/2→N
1+K-2N→M
{17,32,53,78,106,134,154,192,230,271,321
If M=2:{25,47,77,114,154,195,224,279,335,395,468
1+sum(Ans<N→V
If V>11:Stop
FnOff :AxesOff:GridOff:PlotsOff :ClrDraw:DispGraph
Asm(prgmθQR
Pause 
```

1. The first call (V=0) checks the text. Ans is 2·length+1 if it will be encoded
   alphanumeric, 2·length for byte mode, or 65532 or more for an error. The program sets
   M from that last bit (1 byte, 2 alphanumeric), so the draw call uses the same mode.
2. The program then picks the smallest version whose capacity holds the length, from the
   table for that mode (the capacity tables are below).
3. The second call draws the code on the graph screen.

`Stop` here stands for your own error handling. A message too long for version 11
(321 characters, or 468 alphanumeric) has to be split: see "Splitting" below.

## Input variables

| Var | Meaning |
| --- | --- |
| E | What to encode: **1** Str1, **2** the Notefolio note named in Str2, **3** list Notefolio notes (see below) |
| V | **0** = check only (E=1 or 2); **1-11** = draw a code of that version |
| M | Text mode: **0** auto, **1** byte (ASCII), **2** alphanumeric only. Auto uses alphanumeric if every character allows it, else byte; the check's Ans says which (odd = alphanumeric), and the engine never changes M, so set M to 1 or 2 from it before drawing. A draw call with M=0 decides again by reading the text; pick its version by the byte capacity if you haven't checked |
| N | Number of characters to encode. **Must fit the version's capacity**; the engine doesn't check. It is cut to the input's length |
| O | Number of characters to skip first (for splitting; 0 = from the start) |

A variable that doesn't exist reads as 0, so you only need to set the ones that matter.
A draw call also reads N and O; the check call reads only E, V and M. (A, which used to carry the check's choice, is no longer read.)

## Return values (Ans)

| Ans | Meaning |
| --- | --- |
| 0 | Drawn (V=1-11) |
| 2·L + 1, 2·L | Check (V=0): length L (at most 32765); +1 means it will be encoded alphanumeric |
| 65533 | A character can't be encoded (its position is in B): a token with no ASCII equivalent (`sin(`, `π`, ...), or a character that isn't alphanumeric when M=2 |
| 65532 | Check: longer than 32765 characters |
| 65535 | Bad parameters (E, V or M out of range), or the input doesn't exist (no Str1, no such note) |

Tip: store 65534 to Ans right before `Asm(prgmθQR`. If the engine can't run at all, Ans
stays 65534, and your error check catches it.

## What it changes

- **Graph screen:** draws the code centered on the graph buffer, then DispGraph. It only
  sets dark modules, so ClrDraw first.
- Before calling it, turn off anything the OS would redraw over the code: `FnOff`, `AxesOff`,
  `GridOff`, `PlotsOff`, then `ClrDraw` and `DispGraph`. Otherwise the OS can redraw the graph
  screen later and erase the code.
- **Variables:** it writes only Ans, plus:
  - **B**, the position of the first problem character: the one that can't be encoded
    (Ans 65533), or, for a note in byte mode, the first non-ASCII character (a warning:
    the code is still checked or drawn). Left unchanged if there's none, so set B to 0 first.
  - **Str3**, for E=3.
- **Scratch RAM:** it uses L₁ (saveSScreen) and L₃ (appBackUpScreen), the usual scratch areas.

## Capacity per version (error correction level L)

| Version | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Size (modules = pixels) | 21 | 25 | 29 | 33 | 37 | 41 | 45 | 49 | 53 | 57 | 61 |
| Byte mode | 17 | 32 | 53 | 78 | 106 | 134 | 154 | 192 | 230 | 271 | 321 |
| Alphanumeric | 25 | 47 | 77 | 114 | 154 | 195 | 224 | 279 | 335 | 395 | 468 |

Version 11 is the largest that fits the 64-pixel screen.

## Characters

- **Str1** is read token by token. Tokens that are a single ASCII character (letters,
  digits, punctuation, lowercase letters, `"` typed at an Input prompt) encode as that
  character. The negative sign `⁻` is not the minus sign `-` and fails like any other
  non-ASCII token. Anything else fails with 65533 (position in B).
- **Alphanumeric mode** holds only `0-9 A-Z`, space and `$%*+-./:`.
- **Notes** never fail in byte mode. Each calculator character becomes its own byte:
  - θ, ⁴ and the calculator's 0Ah character are swapped with `[`, `$` and Enter;
  - Enter becomes a newline, and the space at a wrapped line becomes a space;
  - other non-ASCII characters keep their code, so a scanner shows their Latin-1 meaning
    (λ C2h → Â).

## Splitting long input

Use the same version for every piece, encode N characters per call, and step O by N:
O=0, then N, then 2N, and so on. Each piece is an ordinary QR code. For auto mode, check
once, set M from its Ans, and every piece then uses that mode. prgmQR's Lbl Q and Lbl H do exactly this.

## Notefolio notes

- **E=3** lists the notes in RAM and archive:
  - Ans = the number of notes;
  - Str3 = their names, 8 characters each (padded with spaces), followed by 48 spaces.
- **E=2** reads the note whose name is in Str2, padded with spaces or not. Use it like E=1.
  Positions count calculator characters. A check also sets B, as described above.
