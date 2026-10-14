INVENTORY

prgmQRBASIC (main program)
prgmθQRBIT (helper program)
ʟGFX (Galois field exponents)
ʟGFL (Galois field logarithms)
ʟXOR (xor table; optional)

prgmQRDATA can regenerate the three lists. Note that it is a very small program, so it may be easier to simply erase the lists when not using them and regenerate them when needed rather than archiving/unarchiving them.

HOW TO RUN

Run prgmQRBASIC from the main menu and make sure the helper program and the three lists are unarchived. Choose ASCII from the main menu, type in your message, and wait up to 10 minutes for the program to finish, depending on the length of your message.

TEN MINUTES?

Yeah. And actually, before several rounds of opimizations, it used to be more like 20. See, there's this thing called "bitwise xor" that's one of the easiest operations a computer can do. Easier than multiplication and even addition. And guess what? The TI-84+ can indeed perform this operation, but not in any way that's accessible to the user. (Note that there is an "xor" command, but it's a logical xor, not bitwise.)

Anyway, there are two ways to do a bitwise XOR using "normal" math. The first involves imaginary numbers and I'm convinced only a madman could have figured it out. I found the algoritm on an old Cemetech thread here: https://www.cemetech.net/forum/viewtopic.php?t=9905

:int(log(2)⁻¹log(max(A,B
:2^cumSum(binomcdf(Ans,0
:sum(Ans.5(1=abs(int(2fPart(Ans⁻¹(A+B𝑖

Weregoose, you are a madman. (Props to KermMartian too for refining it.) It took me a while to figure out what's really going on mathematically, and I quickly lose my grasp on it after I stop thinking about it. If you pre-cache the powers of 2 (what the binomcdf line generates), you can do about 3 xors a second. For reference, your average laptop can do several billion.

My good friend Claude came up with a faster method, but you have to precache a 256-element "nibble" table. (A nibble is half a byte.) It can then compute the XOR of the 4 high bits and 4 low bits by looking them up in a table. It's about twice as fast, but more memory-intensive. You can choose which algorithm you want to use in the options menu.

WHO CARES?

Why would you potentially wait ten minutes for your calculator to generate a QR code that you're just going to scan with your phone?

Well, first of all, it's only 30 seconds for a small (version 1) code.  But I admit this isn't practical. Honestly, I just wanted to make a pure BASIC QR code generator to prove that it was possible, and, well, here it is. If you want actual functionality, I have a sister project where the encoding and drawing functions are written in assembly and it literally takes one second, and it even lets you load NoteFoilo files as the input. It still uses a BASIC program as a wrapper with a similar interface.

ASCII MODE

The TI-83+ does support every ASCII character, though not all of them can be typed with the regular keys (like semicolon). Also note that the negative and minus signs are different (only the minus sign is valid ASCII).  Oh yeah, and you also have to use π (pi) instead of quotation marks. You may be aware that, since the calculator has no escape metacharacter for strings, it's impossible to put a quotation mark in a string. (Or is it? You actually can do it if you manually enter quotation mark when prompted by the Input command within a program, or transfer the string directly to your calculator.) But since we can't set it programatically, I use the pi symbol in its place, since it's convenient to type.

However, if you want to fix the ASCII string yourself (I use Str3 as our alphabet: ASCII characters 32 to 127), I've created an option that tells the program not to overwrite Str3. You can even come up with an entirely new character set if you want. Note that if Str3 doesn't contain exactly 95 characters (perhaps because a different program did something with it), then you'll be back to the old ASCII-with-pi character set. Why does this need to be an option at all, you might ask? Isn't it safe enough to just do that length=95 check? In some world, I'm sure it is, but in ours, there's actually no way to check if a string is defined in TI-Basic without erroring out of it doesn't. Enabling this option really just tells the program to assume Str3 exists in some form.

ALPHANUMERIC MODE

Because the calculator uses all upper-case letters by default, I figured Alphanumeric would be the premier encoding mode, as it lets you use the 10 digits, 26 upper-case letters, a space, and 8 punctuation characters. What more could you want? The problem is, these punctuation appear to have been chosen for encoding URIs and other technical stuff, and aren't ideal for composing a message. They are (enclosed in quotation marks) "$%*+-./:". Dollar sign and percent? Really? Could I please have a question mark or even a comma?

To address this, I created my own set of punctuation optimized for natural English: "?;',-.!:". Three of these are the same (hyphen, period, colon) and the rest are positioned so they line up with the symbol that looks the most similar. If you enable this mode, you can use this alternate set of punctuation, although if you scan the code on your phone, they'll get mapped back to the standard symbols. Depending on what you want to do with the data, you can write your own program on the other end that translates these characters back to the "useful" ones, but that's up to you.

BINARY MODE

To use this mode, you must first store your binary data in list BIN (perhaps with the list editor) and then select Binary encoding. Unlike Alphanumeric and ASCII mode, Binary mode does not prompt you to input the data and assumes list BIN has already been set up.

REDRAW

Tells the program to draw a QR code based on whatever data exists in list CW (codewords). This can be useful if your QR code got erased but the data is still in memory. This is mostly just for testing purposes, though. Rememer, you can turn on the "StorePic 1" option to automatically save the code when it finishes drawing.

THE PROCESS



STATISTICS

Ver:   QR code version. Note that "version" in QR code context just refers to the dimensions, as opposed to some previous standard. They are different "versions" in the sense that they may feature different layouts. Version 11 is 61x61 pixels and is the largest size that can be displayed on the calculator screen.
Size:  dimensions in pixels (all QR codes are square)
Bin:   max encodable bytes or ASCII chars
Alnum: max encodable alphanumeric chars
ʟCW:   finished length of the CW list (Useful for testing; for example, you can run randInt(0,255,405->CW and then run a redraw to test version 11. Note that you won't get a valid, scannable QR code, though.)
Enc:   Time to build the codewords.
ECC:   Time to calculate the error-correcting codes (the real bottleneck, where the xors are)
Draw:  Time to draw the QR code to the graph. This part is the most optimized and I'd be surprised if anyone could meaningfully speed it up.

| Ver | Size | Bin | Alnum | ʟCW | Enc | ECC   | Draw  | TOTAL TIME | Char/sec |
|   1 |   21 |  17 |    25 |  27 |  3s |   14s |   13s |        30s | 1.20     |
|   2 |   25 |  32 |    47 |  45 |  5s |   29s |   20s |        54s | 1.15     |
|   3 |   29 |  53 |    77 |  71 |  9s | 1m02s |   31s |      1m42s | 1.32     |
|   4 |   33 |  78 |   114 | 101 | 12s | 1m51s |   43s |      2m42s | 1.42     |
|   5 |   37 | 106 |   154 | 135 | 17s | 3m07s |   57s | !!!  4m21s | 1.69     |
|   6 |   41 | 134 |   195 | 173 | 21s | 2m59s | 1m12s |      4m32s | 1.39     |
|   7 |   45 | 154 |   224 | 197 | 24s | 3m43s | 1m26s |      5m33s | 1.49     |
|   8 |   49 | 192 |   279 | 243 | 31s | 5m21s | 1m45s |      7m36s | 1.63     |
|   9 |   53 | 230 |   335 | 293 | 38s | 7m42s | 2m05s | !!! 10m25s | 1.86     |
|  10 |   57 | 271 |   395 | 347 | 46s | 6m05s | 2m25s |      9m16s | 1.40     |
|  11 |   61 | 321 |   468 | 405 | 55s | 7m49s | 2m49s |     11m33s | 1.48     |

Performance tests were done with a TI-84+ Silver Edition with relatively new batteries. (XOR tables are enabled.)

Note that v9 is slower than v10! This is because v10 uses four relatively small ECC blocks, while v9 uses two larger ones, with fewer xor operations in total. For this reason, we have a special check that always skips v9 unless chosen manually. v6 actually outperforms v5 during the ECC phase for a similar reason (it's where it jumps from one large block to two smaller ones), and with the XOR table turned off, the gap widens and v6 wins in total time. If you have the XOR table turned off, we'll skip v5 too.

Char/sec measures alphanumeric characters processed per second.

MEMORY USAGE

It depends on how much text you're encoding, but you'll need about 5000 bytes free to fully build the codeword list for version 11.

VARIABLES USED

This program uses almost all of the letter variables, all 6 built-in lists, and Strings 1, 2, and 3.
