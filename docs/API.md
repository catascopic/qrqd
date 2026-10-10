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
int(K/2→N
K-2N→A
{17,32,53,78,106,134,154,192,230,271,321
If A:{25,47,77,114,154,195,224,279,335,395,468
1+sum(Ans<N→V
If V>11:Stop
FnOff :AxesOff:GridOff:PlotsOff :ClrDraw:DispGraph
Asm(prgmθQR
Pause 
```

1. The first call (V=0) checks the text. Ans is 2·length+1 if the text can be encoded
   alphanumeric, 2·length if it needs byte mode, or 32768 or more for an error.
2. The program then picks the smallest version whose capacity holds the length (the
   capacity tables are below).
3. The second call draws the code on the graph screen.

`Stop` here stands for your own error handling. A message too long for version 11
(321 characters, or 468 alphanumeric) has to be split: see "Splitting" below.

## Input variables

| Var | Meaning |
| --- | --- |
| E | What to encode: **1** Str1, **2** list ʟBIN (one byte per element, 0-255), **3** the Notefolio note named in Str3, **4** list Notefolio notes (see below) |
| V | **0** = check only (E=1 or 3); **1-11** = draw a code of that version |
| M | Text mode for E=1 and 3: **0** auto (alphanumeric if every character allows it, else byte), **1** byte (ASCII), **2** alphanumeric only. Ignored for ʟBIN |
| N | Number of characters (or list elements) to encode. **Must fit the version's capacity**; the engine doesn't check. It is cut to the input's length |
| O | Number of characters to skip first (for splitting; 0 = from the start) |
| A | Auto mode only: **1** to encode alphanumeric, as the check call said (Ans odd), **0** for byte mode |

A variable that doesn't exist reads as 0, so you only need to set the ones that matter.
For example, without A an auto-mode code is drawn in byte mode, which can encode
anything. Each draw call reads N, O and A; the check call reads only E, V and M.

## Return values (Ans)

| Ans | Meaning |
| --- | --- |
| 0 | Drawn (V=1-11) |
| 2·L + 1, 2·L | Check (V=0): length L; +1 means it can be encoded alphanumeric |
| 32768 + k | Character k can't be encoded: a token with no ASCII equivalent (`sin(`, `π`, ...), or a character that isn't alphanumeric when M=2 |
| 65532 | Check: longer than 16383 characters |
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
  - **B**, for a check of a note (E=3) in byte mode: the position of the first non-ASCII
    character. Left unchanged if there's none, so set B to 0 first.
  - **Str2**, for E=4.
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
once and pass the same A to every piece. prgmQR's Lbl Q and Lbl H do exactly this.

## Notefolio notes

- **E=4** lists the notes in RAM and archive:
  - Ans = the number of notes;
  - Str2 = their names, 8 characters each (padded with spaces), followed by 48 spaces.
- **E=3** reads the note whose name is in Str3, padded with spaces or not. Use it like E=1.
  Positions count calculator characters. A check also sets B, as described above.
