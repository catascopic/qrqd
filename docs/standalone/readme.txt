QR CODE GENERATOR (TI-83+/84+)

Draws QR codes on the graph screen from a message you type, a NoteFolio note, or a list of bytes. A BASIC program (prgmQR) handles the menus, and an assembly program (prgmθQR) does the encoding, error correction and drawing.

Works on the TI-83+ family. The engine switches to 15 MHz (fast mode) where the calculator supports it, so a plain TI-83 Plus is slightly slower.

SETUP

Keep prgmθQR in RAM (not archived). Running it also needs free RAM at least the size of prgmθQR, because Asm( makes a copy to run. If you get ERR:MEMORY, free up some RAM.

Run prgmQR. If prgmQR stops with an error at Asm(prgmθQR or shows "Error in Asm", make sure prgmθQR exists and isn't archived.

MAIN MENU

1. Message: type your text at the msg= prompt and press Enter.
2. NoteFolio: pick a NoteFolio note (in RAM or archived) from a list, 5 per page. "More" shows the next page and "Back" the previous one (or the main menu).
3. Binary: encodes list BIN, one byte (0-255) per element. Fill in ʟBIN first, for example in the list editor.
4. Set version: 0 picks the smallest code that fits (the default). 1-11 always uses that size: 1 is 21x21 pixels, 11 is 61x61, the largest that fits on the screen.
5. Mode: Auto, ASCII or Alnum. Press it to cycle. Auto uses alphanumeric mode when every character allows it (it fits more text in the same size) and ASCII otherwise. It applies to messages and notes, not binary.
6. Exit

LONG MESSAGES

If a message doesn't fit in one code, it's split into several codes of the same size (version 11, or the version you set). Each one is an ordinary QR code that any scanner reads. A counter like 2/5 shows at the right edge of the screen.
Usually the program ends right after drawing the QR code. But if there are multiple "pages", it enters a waiting state (in the BASIC program), where you can press one of four keys.
Enter or right arrow: next code
Left arrow: previous code
Clear: stop

The most you can encode at once is 16383 characters.

CHARACTERS

ASCII mode encodes letters (including lowercase), digits and the punctuation on the calculator. The negative sign encodes as a minus. Tokens like sin( or π have no ASCII equivalent: you get ERR:BAD CHAR with the character and its position. Press 2nd RCL Str1 at the msg= prompt to get your message back and fix it.

Alphanumeric mode only has 0-9, A-Z, space and $%*+-./: (no lowercase). With Mode set to Alnum, anything else gives ERR:NOT ALNUM.

Notes never fail in ASCII mode. If a note has characters outside ASCII (Greek letters, accented letters), you get a warning with the first position, then it's encoded anyway; each character keeps its calculator code. Scanning it may show arbitrary characters (λ shows as Â).

VARIABLES USED

prgmQR overwrites these: Str1 (your message), Str2 (the note name), Str3 (the list of note names), L1, and the real variables A, B, C, E, I, J, K, L, M, N, O, P, U, V and W. It also clears the graph screen and turns off functions, plots, axes and the grid.

USING THE ENGINE FROM YOUR OWN PROGRAM

prgmθQR can be called from any BASIC program: set a few variables, run Asm(prgmθQR), and read Ans.
