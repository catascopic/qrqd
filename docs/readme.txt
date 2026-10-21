What if I told you... that I can run a program on my calculator to wirelessly transmit data to my phone? Would you believe me?

That's exactly what this program does. Simply type in a message or select one of your NoteFolio files. A BASIC program (prgmQR) handles the user interface (I do love a good BASIC Menu), and an assembly program (prgmθQR) does the encoding, error correction, and drawing.

Works on the TI-83+ family. The engine switches to 15 MHz (fast mode) where the calculator supports it, so a plain TI-83+ is slightly slower.

Full credit to Claude for writing the assembly code (yes, Claude can write z80 assembly)! I take solace in having written a pure BASIC QR code generator all by myself, though it's not exactly practical (see below for details).

SETUP

Run prgmQR. It will call prgmθQR, so keep it unarchived. You will also need free RAM at least the size of prgmθQR, because Asm( makes a copy to run. If you get ERR:MEMORY, free up some RAM.

MAIN MENU

1. Message: type your text at the msg= prompt.
2. NoteFolio: pick a NoteFolio file (in RAM or archived) from a list. "More" shows the next page and "Back" the previous one (or the main menu).
3. Set version: 0 for automatic mode (the default), the smallest version that fits. 1-11 always uses that size: 1 is 21x21 pixels, 11 is 61x61, the largest that fits on the screen. Note that "version" in the context of QR codes just refers to the size, as opposed to some previous standard. They are different "versions" in the sense that they may feature different layouts.
4. Mode: Auto, ASCII or Alnum. Press it to cycle. Auto uses alphanumeric mode when every character allows it (it fits more text in the same size) and ASCII otherwise. It applies to messages and files.
5. Exit

CHARACTERS

ASCII mode encodes letters (including lowercase), digits and the punctuation on the calculator. Tokens like "sin(" or "π" (or, notably, the calculator's "negative" symbol) have no ASCII equivalent; you get ERR:BAD CHAR with the character and its position. Press 2nd RCL Str1 at the msg= prompt to get your message back and fix it.

Alphanumeric mode only has 0-9, A-Z, space and $%*+-./: (no lowercase). With Mode set to Alnum, anything else gives ERR:NOT ALNUM.

NoteFolio files never fail in ASCII mode. If a file has characters outside ASCII (Greek letters, accented letters), you get a warning with the first position, then it's encoded anyway; each character keeps its calculator code. Scanning it may show arbitrary characters (λ shows as Â).

QR CODE VERSIONS

This table shows the maximum capacity of each version for both ASCII and alphanumeric characters. "Size" is the height/width of the code in pixels.

| Ver | Size | ASCII | Alnum |
|   1 |   21 |    17 |    25 |
|   2 |   25 |    32 |    47 |
|   3 |   29 |    53 |    77 |
|   4 |   33 |    78 |   114 |
|   5 |   37 |   106 |   154 |
|   6 |   41 |   134 |   195 |
|   7 |   45 |   154 |   224 |
|   8 |   49 |   192 |   279 |
|   9 |   53 |   230 |   335 |
|  10 |   57 |   271 |   395 |
|  11 |   61 |   321 |   468 |

LONG MESSAGES

If a message doesn't fit in one code, it's split into several codes of the same size (automatically chosen, or the version you set). Each one is an ordinary QR code that any scanner reads. A counter like 2/5 shows at the right edge of the screen.
Usually the program ends right after drawing the QR code. But if there are multiple "pages", it enters a waiting state (in the BASIC program), where you can press one of four keys.
Enter or right arrow: next code
Left arrow: previous code
Clear: stop

The most you can encode at once is 32765 characters.

ERRORS

ERR:ENGINE with a code means prgmθQR couldn't do the job. Code=65534: prgmθQR didn't run (for unknown reasons). Code=65535: bad input, for example a NoteFolio file that somehow was deleted after the list was shown.

VARIABLES USED

prgmQR overwrites these: Str1 (your message), Str2 (the file name), L6, and the real variables B, C, D, E, I, J, K, L, M, N, O, P, U, V and W. It deletes Str3, which holds the list of file names while you pick one. It also clears the graph screen and turns off functions, plots, axes and the grid.

USING THE ENGINE FROM YOUR OWN PROGRAM

prgmθQR can be called from any BASIC program: set a few variables, run Asm(prgmθQR), and read Ans. A variable that doesn't exist counts as 0.

E: controls what the program does.
E=1: Encode the text in Str1
E=2: Encode the NoteFolio file whose name is in Str2
E=3: Stores the names of all NoteFolio files into Str3, 8 characters each (padded with spaces); return the number of files in Ans.

V: the version
V=0: only check the text (for a string or NoteFolio file)
V=1..11: draw a code of that version

M: encoding mode (used with E=1 and 2 only)
M=0: auto: the engine picks alphanumeric if every character allows it
M=1: ASCII
M=2: alphanumeric

N: how many characters to encode. It must fit the version; the engine doesn't check

O: how many characters to skip first (for splitting a long message; use 0 normally)

Note that if either V or M are 0 when you call prgmθQR, it runs "check mode", and returns a 16-bit integer representing the mode and the number of characters. Then it passes control back to the BASIC program to set V and M, where you can call prgmθQR again to do the actual drawing.

Ans: What the program did.
Ans=0: QR code drawn successfully
0<Ans<65533: The result of "check mode"; nothing drawn. The least significant bit is the mode (1 for alphanumeric, 0 for ASCII); use iPart(Ans/2) to get the length and fPart(Ans/2) to get the mode.
Ans=65533: A character can't be encoded; B holds its position
Ans=65532: Input was longer than 32765 characters
Ans=65535: Bad value for E, V, or M, or the input doesn't exist

B (set it to 0 first) gets the position of the first problem character: the one that can't be encoded (65533), or, for a file in ASCII mode, the first non-ASCII character (just a warning; the check still succeeds).

Example: draw "HELLO WORLD" as a version 1 code in ASCII mode.
"HELLO WORLD→Str1
1→E:1→M:1→V:0→O:17→N
FnOff:AxesOff:GridOff:PlotsOff:ClrDraw:DispGraph
Asm(prgmθQR

PURE BASIC VERSION

Just for fun, I have a pure BASIC QR code generator, though it's super slow because there is no bitwise xor in BASIC! For a v11 QR code, it takes 8 minutes to do all the math, and then another 3 minutes to draw. It's completely impractical, but it was an interesting challenge.
