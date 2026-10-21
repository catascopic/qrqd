QR CODE GENERATOR

Draws QR codes on the graph screen from a message you type or a NoteFolio file. A BASIC program (prgmQR) handles the menus, and an assembly program (prgmθQR) does the encoding, error correction and drawing.

Works on the TI-83+ family. The engine switches to 15 MHz (fast mode) where the calculator supports it, so a plain TI-83+ is slightly slower.

SETUP

Run prgmQR. It will call prgmθQR, so keep it unarchived. You will also need free RAM at least the size of prgmθQR, because Asm( makes a copy to run. If you get ERR:MEMORY, free up some RAM.

MAIN MENU

1. Message: type your text at the msg= prompt.
2. NoteFolio: pick a NoteFolio file (in RAM or archived) from a list. "More" shows the next page and "Back" the previous one (or the main menu).
3. Set version: 0 for automatic mode (the default), the smallest version that fits. 1-11 always uses that size: 1 is 21x21 pixels, 11 is 61x61, the largest that fits on the screen.
4. Mode: Auto, ASCII or Alnum. Press it to cycle. Auto uses alphanumeric mode when every character allows it (it fits more text in the same size) and ASCII otherwise. It applies to messages and files.
5. Exit

LONG MESSAGES

If a message doesn't fit in one code, it's split into several codes of the same size (automatically chosen, or the version you set). Each one is an ordinary QR code that any scanner reads. A counter like 2/5 shows at the right edge of the screen.
Usually the program ends right after drawing the QR code. But if there are multiple "pages", it enters a waiting state (in the BASIC program), where you can press one of four keys.
Enter or right arrow: next code
Left arrow: previous code
Clear: stop

The most you can encode at once is 32765 characters.

CHARACTERS

ASCII mode encodes letters (including lowercase), digits and the punctuation on the calculator. The negative sign isn't ASCII (only the minus sign is), so it's a bad character too. Tokens like sin( or π have no ASCII equivalent: you get ERR:BAD CHAR with the character and its position. Press 2nd RCL Str1 at the msg= prompt to get your message back and fix it.

Alphanumeric mode only has 0-9, A-Z, space and $%*+-./: (no lowercase). With Mode set to Alnum, anything else gives ERR:NOT ALNUM.

NoteFolio files never fail in ASCII mode. If a file has characters outside ASCII (Greek letters, accented letters), you get a warning with the first position, then it's encoded anyway; each character keeps its calculator code. Scanning it may show arbitrary characters (λ shows as Â).

VARIABLES USED

prgmQR overwrites these: Str1 (your message), Str2 (the file name), Str3 (the list of file names), L1, and the real variables B, C, D, E, I, J, K, L, M, N, O, P, U, V and W. It also clears the graph screen and turns off functions, plots, axes and the grid.

USING THE ENGINE FROM YOUR OWN PROGRAM

prgmθQR can be called from any BASIC program: set a few variables, run Asm(prgmθQR), and read Ans. A variable that doesn't exist counts as 0.

Use the E variable to control what input the program uses.
E=1: the text in Str1
E=2: the NoteFolio file whose name is in Str2
E=3: lists the NoteFolio files instead. Ans = how many, Str3 = their names, 8 characters each (padded with spaces)

V: version. V=0 only checks the text (for a string or NoteFolio file), V=1..11 draws a code of that version
M: encoding mode. M=0: auto, M=1: ASCII, M=2: alphanumeric (used with E=1 and 2 only). With M=0 the engine picks alphanumeric if every character allows it; a check's Ans tells you which (odd = alphanumeric), so you can set M to 1 or 2 for the drawing calls
N: how many characters to encode. It must fit the version; the engine doesn't check
O: how many characters to skip first (for splitting a long message; use 0 normally)

Ans value:
0: drawn successfully
2*length+1 or 2*length: from a check (V=0); +1 means it will be encoded alphanumeric
65533: a character can't be encoded; B holds its position
65532: longer than 32765 characters
65535: bad value for E, V, or M, or the input doesn't exist
B (set it to 0 first) gets the position of the first problem character: the one that can't be encoded (65533), or, for a file in ASCII mode, the first non-ASCII character (just a warning; the check still succeeds).

Before calling it, run FnOff, AxesOff, GridOff, PlotsOff, ClrDraw and DispGraph, or the OS may redraw the graph screen and erase the code. The code is drawn centered on the graph screen.

Example: draw "HELLO WORLD" as a version 1 code in ASCII mode.
"HELLO WORLD→Str1
1→E:1→M:1→V:0→O:17→N
FnOff:AxesOff:GridOff:PlotsOff:ClrDraw:DispGraph
Asm(prgmθQR
