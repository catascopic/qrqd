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
If K≥32768:Stop
K→N
{17,32,53,78,106,134,154,192,230,271,321
If M=2:{25,47,77,114,154,195,224,279,335,395,468
1+sum(Ans<N→V
If V>11:Stop
FnOff :AxesOff:GridOff:PlotsOff :ClrDraw:DispGraph
Asm(prgmθQR
Pause 
```

1. The first call (V=0) checks the text. Ans is its length, or 32768 or more for an
   error. In auto mode (M=0) it stores the mode it chose in M: 1 byte, 2 alphanumeric
   (with M=1 or 2, M stays as it is).
2. The program then picks the smallest version whose capacity holds the length, from the
   table for that mode (the capacity tables are below).
3. The second call draws the code on the graph screen.

`Stop` here stands for your own error handling. A message too long for version 11
(321 characters, or 468 alphanumeric) has to be split: see "Splitting" below.

## Input variables

| Var | Meaning |
| --- | --- |
| E | What to encode: **1** Str1, **2** list ʟBIN (one byte per element, 0-255), **3** the Notefolio note named in Str2, **4** list Notefolio notes (see below) |
| V | **0** = check only (E=1 or 3); **1-11** = draw a code of that version |
| M | Text mode for E=1 and 3: **0** auto, **1** byte (ASCII), **2** alphanumeric only. Ignored for ʟBIN. Auto reads the text, uses alphanumeric if every character allows it (else byte), and stores its choice (1 or 2) in M, so later calls for the same text use it. A draw call with M=0 and no check first decides the same way; pick its version by the byte capacity, since the mode isn't known in advance |
| N | Number of characters (or list elements) to encode. **Must fit the version's capacity**; the engine doesn't check. It is cut to the input's length |
| O | Number of characters to skip first (for splitting; 0 = from the start) |

A variable that doesn't exist reads as 0, so you only need to set the ones that matter,
except M: always set it. In auto mode the check reports its choice only in M, so without M
you couldn't tell which mode it picked. A draw call also reads N and O; the check call
reads only E, V and M. (A, which used to carry the check's choice, is no longer read.)

## Return values (Ans)

| Ans | Meaning |
| --- | --- |
| 0 | Drawn (V=1-11) |
| L | Check (V=0): the length, 0-32767 (the mode is in M) |
| 32768 + k | Character k can't be encoded: a token with no ASCII equivalent (`sin(`, `π`, ...), or a character that isn't alphanumeric when M=2 |
| 65532 | Check: longer than 32767 characters |
| 65535 | Bad parameters (E, V or M out of range), or the input doesn't exist (no Str1, no ʟBIN, no such note) |

Tip: store 65534 to Ans right before `Asm(prgmθQR`. If the engine can't run at all, Ans
stays 65534, and your error check catches it.

## What it changes

- **Graph screen:** draws the code centered on the graph buffer, then DispGraph. It only
  sets dark modules, so ClrDraw first.
- Before calling it, turn off anything the OS would redraw over the code: `FnOff`, `AxesOff`,
  `GridOff`, `PlotsOff`, then `ClrDraw` and `DispGraph`. Otherwise the OS can redraw the graph
  screen later and erase the code.
- **Variables:** it writes only Ans, plus:
  - **M**, in auto mode (M=0) with E=1 or 3: the mode it chose, 1 or 2. Only if M exists.
  - **B**, for a check of a note (E=3) in byte mode (or a draw with M=0): the position of the first non-ASCII
    character. Left unchanged if there's none, so set B to 0 first.
  - **Str3**, for E=4.
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
  character. The negative sign `⁻` encodes as `-`. Anything else fails with 32768+k.
- **Alphanumeric mode** holds only `0-9 A-Z`, space and `$%*+-./:`.
- **Notes** never fail in byte mode. Each calculator character becomes its own byte:
  - θ, ⁴ and the calculator's 0Ah character are swapped with `[`, `$` and Enter;
  - Enter becomes a newline, and the space at a wrapped line becomes a space;
  - other non-ASCII characters keep their code, so a scanner shows their Latin-1 meaning
    (λ C2h → Â).

## Splitting long input

Use the same version for every piece, encode N characters per call, and step O by N:
O=0, then N, then 2N, and so on. Each piece is an ordinary QR code. For auto mode, check
once: the check stores the mode in M, and every piece then uses it. prgmQR's Lbl Q and Lbl H do exactly this.

## Notefolio notes

- **E=4** lists the notes in RAM and archive:
  - Ans = the number of notes;
  - Str3 = their names, 8 characters each (padded with spaces), followed by 48 spaces.
- **E=3** reads the note whose name is in Str2, padded with spaces or not. Use it like E=1.
  Positions count calculator characters. A check also sets B, as described above.
