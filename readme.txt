QUICK GUIDE

Choose ASCII from the main menu, type in your message, and wait about 1 to 15 minutes for the program to finish, depending on the length of your message.

15 MINUTES?

Yeah. See, there's this elementary operation called "bitwise xor" that, for a computer, is one of the easiest things it can do. Easier than multiplication and even addition. And guess what? The TI-84+ has no way to perform this operation that the user has access to. (Note that there is an "xor" command, but it's a logical xor, not bitwise.)

Anyway, there are two ways to do a bitwise XOR using "normal" math. The first involves imaginary numbers and I'm convinced only a madman could have figured this out. I found the algoritm on an old Cemetech here: https://www.cemetech.net/forum/viewtopic.php?t=9905

:int(log(2)⁻¹log(max(A,B
:2^cumSum(binomcdf(Ans,0
:sum(Ans.5(1=abs(int(2fPart(Ans⁻¹(A+B𝑖

Weregoose, you are a madman. It took me a while to figure out what was really going on here, and I quickly lose my grasp on it once I stop thinking about it. If you pre-cache the powers of 2 (what the binomcdf line does), you can do about 3 xors a second. For reference, your average laptop can do several billion.

My good friend Claude came up with a slightly faster method, but you have to precache a 256-element "nibble" table. (A nibble is half a byte.) It can then compute the XOR of the 4 high bits and 4 low bits by looking them up in a table. It's much faster, but more memory-intensive. You can choose which algorithm you want to use in the options menu.

WHO CARES?

Why would you potentially wait up to 15 minutes for your calculator to generate a QR code that you're just going to scan with your phone? Honestly, this program is just a proof of concept. I wanted to make a pure BASIC QR code generator, and here it is. If you want actual functionality, I have a sister project where the encoding and drawing functions are written in assembly and it literally takes one second. It still uses a BASIC program as a wrapper with a similar interface, but it also lets you load NoteFoilo files to encode rather than only accepting String input.

ASCII MODE

The TI-83+ does support every ASCII character, though not all of them can be typed with the regular keys (like semicolon). Also note that the negative and minus signs are different, and only the minus sign is valid ASCII.  Oh yeah, and you also have to use π (pi) instead of quotation marks.

You may be aware that, since the calculator has no escape metacharacter for strings, it's impossible to put a quotation mark in a string. Or is it? You actually can do it if you manually enter quotation mark when prompted by the Input command within a program, or transfer the string directly to your calculator. But since we can't set it programatically, I use the pi symbol in its place, since it conveniently has its own key.

However, if you want to fix the ASCII string yourself (I use Str3 as our alphabet: ASCII characters 32 to 127), I've created an option that tells the program not to overwrite Str3. You can even come up with an entirely new character set if you want. Note that if Str3 doesn't contain exactly 95 characters (perhaps because a different program did something with it), then you'll be back to the old ASCII-with-pi character set. Why does this need to be an option at all, you might ask? Isn't it safe enough to just do that length=95 check? Indeed it should be, but there's actually no way to check if a string is defined in TI-Basic without erroring out of it doesn't. Enabling this option really just tells the program to assume Str3 exists in some form.

ALPHANUMERIC MODE

Because the calculator uses all upper-case letters by default, I figured Alphanumeric would be the premier encoding mode, as it lets you use the 10 digits, 26 upper-case letters, a space, and 8 punctuation characters. What more could you want? The problem is, these punctuation appear to have been chosen for encoding URIs and other technical stuff, and aren't ideal for composing a message. They are (enclosed in quotation marks) "$%*+-./:". Dollar sign and percent? Really? Could I please have a question mark or even a comma?

To address this, I created my own set of punctuation optimized for natural English: "?;',-.!:". Three of these are the same (hyphen, period, colon) and the rest are positioned so they line up with the symbol that looks the most similar. If you enable this mode, you can use this alternate set of punctuation, although if you scan the code on your phone, they'll get mapped back to the standard symbols. Depending on what you want to do with the data, you can write your own program on the other end that translates these characters back to the "useful" ones, but that's up to you.

BINARY MODE

To use this mode, you must first store your binary data in list BIN (perhaps with the list editor) and then select Binary encoding. Unlike Alphanumeric and ASCII mode, Binary mode does not prompt you to input the data and assumes list BIN has already been set up.

REDRAW

Tells the program to draw a QR code based on whatever data exists in list CW (codewords). This can be useful if your QR code got erased but the data is still in memory. This is mostly just for testing purposes, though. Turn on the "StorePic 1" option to automatically save the code when it finishes drawing.

PERFORMANCE

This table displays the time for generating each version (size) of a QR code. Version 11 is 61x61 pixels and is the largest size that can be displayed here, so the program only supports versions 1 to 11. Note that XOR tables are enabled for these runs.

| Ver | Size | Bin | Alnum | Enc | ECC   | Draw  | TOTAL TIME | Char/sec |
|   1 |   21 |  17 |    25 |  3s |   14s |   15s |        32s | 1.28     |
|   2 |   25 |  32 |    47 |  5s |   29s |   29s |        63s | 1.34     |
|   3 |   29 |  53 |    77 |  9s | 1m02s |   42s |      1m53s | 1.47     |
|   4 |   33 |  78 |   114 | 12s | 1m51s |   59s |      3m02s | 1.60     |
|   5 |   37 | 106 |   154 | 17s | 3m07s | 1m17s | !!!  4m41s | 1.82     |
|   6 |   41 | 134 |   195 | 21s | 2m59s | 1m37s |      4m57s | 1.52     |
|   7 |   45 | 154 |   224 | 24s | 3m43s | 2m17s |      6m24s | 1.74     |
|   8 |   49 | 192 |   279 | 31s | 5m21s | 2m48s |      8m40s | 1.86     |
|   9 |   53 | 230 |   335 | 38s | 7m42s | 3m12s | !!! 11m32s | 2.07     |
|  10 |   57 | 271 |   395 | 46s | 6m05s | 3m50s |     10m41s | 1.62     |
|  11 |   61 | 321 |   468 | 55s | 7m49s | 4m22s |     13m06s | 1.68     |

Note that v9 is slower than v10! This is because v10 uses four relatively small ECC blocks, while v9 uses two larger ones, with fewer xor operations in total. For this reason, we have a special check that always skips v9 unless chosen manually. v6 actually outperforms v5 during the ECC phase for a similar reason (it's where it jumps from one large block to two smaller ones), and with the XOR table turned off, the gap widens and v6 wins in total time. If you have the XOR table turned off, we'll skip v5 too.



MEMORY USAGE:

Does CW get copied at all?

VARIABLES USED

Str1: User input
Str2: Alphanumeric character set
Str3: ASCII character set (see "ASCII FIX")
L1-L6: Temporary data, mostly ECC bytes
listCW: Codewords. Contains the bytes used to draw the QR code.
listQR: Options