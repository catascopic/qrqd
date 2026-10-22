Draws QR codes on the graph screen from a message you type or a NoteFolio file. A BASIC program handles the user interface (I do love a good BASIC Menu), and an assembly program does the encoding, error correction, and drawing. Works on the monochrome TI-83+ family.

Full credit to Claude for writing the assembly code (yes, Claude can write Z80 assembly)! I take solace in having written a pure BASIC QR code generator all by myself, though it's not exactly practical (see below for details).

SETUP

Run prgmQR. It will call prgmθQR, so keep it unarchived. You will also need free RAM at least the size of prgmθQR, because Asm( makes a copy to run. If you get ERR:MEMORY, free up some RAM.

MAIN MENU

1. Message: type your text at the msg= prompt.
2. NoteFolio: pick a NoteFolio file (in RAM or archived) from an alphabetical list. "Next" shows the next page if available and "Back" returns to the previous page or the main menu.
3. Set version: 0 for automatic mode (the default), which picks the smallest version that fits. 1-11 always uses that size: 1 is 21x21 pixels, 11 is 61x61, the largest that fits on the screen. (Note that "version" in the context of QR codes just refers to the size, as opposed to different standards. They are different "versions" in the sense that they may feature different layouts.)
4. Mode: Auto, ASCII or Alnum. Press it to cycle. Auto uses alphanumeric mode when every character allows it (it fits more text in the same size) and ASCII otherwise. It applies to messages and files.
5. Exit

CHARACTERS

ASCII mode encodes letters (including lowercase), digits and the punctuation on the calculator. Tokens like "sin(" or "π" (or, notably, the calculator's "negative" symbol) have no ASCII equivalent; you get ERR:BAD CHAR with the character and its position. Use RCL on Str1 at the msg= prompt to get your message back and fix it.

Alphanumeric mode only has 0-9, A-Z, space and $%*+-./: (no lowercase). With Mode set to Alnum, anything else gives ERR:NOT ALNUM.

NoteFolio files never fail in ASCII mode. If a file has characters outside ASCII (Greek letters, accented letters), you get a warning with the first position, then it's encoded anyway; each character keeps its calculator code. Scanning it will show the characters' Latin-1 equivalents (λ becomes Â).

QR CODE VERSIONS

This table shows the maximum capacity of each version for both ASCII and alphanumeric characters. "Size" is the height/width of the code in pixels.

| Version |   1 |   2 |   3 |   4 |   5 |   6 |   7 |   8 |   9 |  10 |  11 |
| Size    |  21 |  25 |  29 |  33 |  37 |  41 |  45 |  49 |  53 |  57 |  61 |
| ASCII   |  17 |  32 |  53 |  78 | 106 | 134 | 154 | 192 | 230 | 271 | 321 |
| Alnum   |  25 |  47 |  77 | 114 | 154 | 195 | 224 | 279 | 335 | 395 | 468 |

LONG MESSAGES

If a message doesn't fit in one code, it's split into several codes of the same size (automatically chosen, or the version you set). Each one is an ordinary QR code that any scanner reads. A counter like 2/5 shows at the right edge of the screen.
Usually the program ends right after drawing the QR code. But if there are multiple "pages", it enters a waiting state (in the BASIC program), where you can press one of four keys.
Enter or right arrow: next code
Left arrow: previous code
Clear: stop

The most you can encode at once is 32765 characters.

CUTTING CORNERS

In order to keep this program small and fast, we're not generating our QR codes in the recommended way. QR codes have four levels of error correction: Low, Medium, Quartile, and High. This program is hard-coded for Low mode, which lets you store more data per code at the cost of being able to survive less damage, which is mostly relevant for QR codes printed on paper anyway.

Then there's the "masking" phase, where, after processing the input, the generator is supposed to "try on" eight different masks (basically different ways of displaying the code) and score each one for readability using a complex algorithm that basically tries to minimize large clusters of all-white or all-black pixels, or things that look like alignment patterns. This would be possible but would add a ton of extra code, so we just apply Mask 0 and say good enough. In theory this could generate codes that are a difficult to scan, but remember: QR codes were invented in the 90s. Our technology is way better now, and we can get away with a lot before actually running into problems. Personally, I've never generated a code with this program that wouldn't scan.

VARIABLES USED

prgmQR overwrites these: Str1 (your message), Str2 (the file name), L6, and the real variables B, C, D, E, I, J, K, L, M, N, O, P, U, V and W. It deletes Str3, which holds the list of file names while you pick one. It also clears the graph screen and turns off functions, plots, axes and the grid.

USING THE ENGINE FROM YOUR OWN PROGRAM

prgmθQR can be called from any BASIC program: set a few variables, run Asm(prgmθQR), and read Ans. A variable that doesn't exist counts as 0.

E: Input type
E=1: Use Str1 as input
E=2: Use the NoteFolio file whose name is in Str2 as input
E=3: Override normal operation. Store the names of all NoteFolio files in Str3 (8 characters each, padded with spaces); return the number of files in Ans.

V: Version
V=0: Check the input without drawing a code. Return a 16-bit integer representing the mode and the number of characters. The least significant bit is the mode (1 for alphanumeric, 0 for ASCII); use iPart(Ans/2) to get the length and 2fPart(Ans/2) to get the mode. A value over 65531 represents an error.
V=1..11: Draw a code of that version.

M: Encoding mode
M=0: ASCII
M=1: alphanumeric

O: Offset
How many characters to skip first (for splitting a long message; use 0 normally)

N: Length
How many characters to encode. It must fit for the given version; the engine doesn't check

Ans: Return code
Ans=0: QR code drawn successfully
Ans=65532: Input was longer than 32765 characters (only for check mode)
Ans=65533: A character can't be encoded; B holds its position
Ans=65534: The engine failed to run for unknown reasons
Ans=65535: Argument error. E, V, or M held an invalid value, or the input doesn't exist. Alternatively, NoteFolio scan mode (E=3) ran out of memory.

In the case of bad input, B holds the position of the first problem character: the one that can't be encoded (65533), or, for a file in ASCII mode, the first non-ASCII character (just a warning; the check still succeeds).

Example: draw "HELLO WORLD" as a version 1 code in ASCII mode.
"HELLO WORLD→Str1
1→E:1→M:1→V:0→O:length(Str1→N
FnOff:AxesOff:GridOff:PlotsOff:ClrDraw:DispGraph
Asm(prgmθQR

PURE BASIC VERSION

Just for fun, I have a pure BASIC QR code generator, though it's super slow because there is no bitwise xor in BASIC! For a v11 QR code, it takes 8 minutes to do all the math, and then another 3 minutes to draw. It's completely impractical, but it was an interesting challenge.
