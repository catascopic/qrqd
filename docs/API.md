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
0→C:0→I:0→M
Asm(prgmθQR
Ans→K
If K≥65532:Stop
int(K/2→N
1+K-2N→M
{17,32,53,78,106,134,154,192,230,271,321
If M=2:{25,47,77,114,154,195,224,279,335,395,468
1+sum(Ans<N→V
If V>11:Stop
1→C:0→O
FnOff :AxesOff:GridOff:PlotsOff :ClrDraw:DispGraph
Asm(prgmθQR
Pause 
```

1. The first call (C=0) checks Str1 (I=0) in auto mode (M=0). Ans is 2·length+1 if it
   will be encoded alphanumeric, 2·length for byte mode, or 65532 or more for an error.
   The program sets M from that last bit (1 byte, 2 alphanumeric) and N to the length.
2. It then picks the smallest version whose capacity holds the length, from the table
   for that mode (the capacity tables are below).
3. The second call (C=1) draws the code on the graph screen.

`Stop` here stands for your own error handling. A message too long for version 11
(321 characters, or 468 alphanumeric) has to be split: see "Splitting" below.

## Input variables

| Var | Meaning |
| --- | --- |
| C | The command: **0** check the input (nothing is drawn), **1** draw one code, **2** list the Notefolio notes into Str3 (see below) |
| I | The input, for C=0 and 1: **0** Str1, **1** the Notefolio note named in Str2 |
| M | The mode, for C=0 and 1: **0** auto (check only), **1** byte (ASCII), **2** alphanumeric only. A check in auto mode uses alphanumeric if every character allows it, else byte, and Ans says which (odd = alphanumeric). A draw needs the mode decided, 1 or 2: set M from the check's Ans. The engine never changes M |
| V | The version, for C=1: **1-11** |
| N | For C=1: the number of characters to encode. **Must fit the version's capacity**; the engine doesn't check. It is cut to the input's length |
| O | For C=1: the number of characters to skip first (for splitting; 0 = from the start) |

A variable that doesn't exist reads as 0, so you only need to set the ones that matter, and
a call with none at all is a check of Str1 in auto mode. Each command ignores the variables
it doesn't use. A draw doesn't read the text first: it trusts the check before it, so check
first, then draw with the mode the check found.

## Return values (Ans)

| Ans | Meaning |
| --- | --- |
| 0 | Drawn (C=1) |
| 2·L + 1, 2·L | Check (C=0): length L (at most 32765); +1 means it will be encoded alphanumeric. In auto mode never 0, so it can't be mistaken for "drawn" |
| K | List (C=2): the number of notes |
| 65533 | Check: a character can't be encoded (its position is in B): a token with no ASCII equivalent (`sin(`, `π`, ...), or a character that isn't alphanumeric when M=2 |
| 65532 | Check: longer than 32765 characters |
| 65535 | Bad parameters (C, I or M out of range; a draw with V not 1-11 or M=0), the input doesn't exist (no Str1, no such note), or not enough free RAM for Str3 (C=2) |

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
  - **Str3**, for C=2.
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

Check once (C=0), set M from its Ans, then draw (C=1) every piece with the same version
and mode, N characters per call, stepping O by N: O=0, then N, then 2N, and so on. Each
piece is an ordinary QR code. prgmQR's Lbl Q and Lbl H do exactly this.

## Notefolio notes

- **C=2** lists the notes in RAM and archive (it reads no other variable):
  - Ans = the number of notes;
  - Str3 = their names, 8 characters each (padded with spaces), in alphabetical order
    (by character code: digits, then A-Z, then θ; a shorter name before a longer one that
    starts the same), then blank names (8 spaces each) up to the end of the last group of 5.
    So Str3's length is a multiple of 40, and reading 5 names from any name that exists
    stays inside it, as prgmQR's pager does; with no notes it is empty;
  - at most 80 notes are listed (the first 80 found);
  - Ans = 65535 if there isn't enough free RAM to make Str3.
- **I=1** reads the note whose name is in Str2, padded with spaces or not, for a check or
  a draw, just as I=0 reads Str1. Positions count calculator characters. A check also sets
  B, as described above.
