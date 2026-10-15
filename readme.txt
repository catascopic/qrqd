CONTENTS

prgmQRBASIC (main program)
prgmθQRBIT (helper program)
ʟGFX (Galois field exponents)
ʟGFL (Galois field logarithms)
ʟXOR (xor table; optional)

HOW TO RUN

Run prgmQRBASIC from the main menu (making sure the helper program and the three lists are unarchived). Choose ASCII from the main menu, type in your message, and wait up to 10 minutes for the program to finish, depending on the length of your message.

TEN MINUTES?

Yeah. And actually, before several rounds of optimizations, it used to be more like 20. See, there's this thing called "bitwise xor" that's one of the easiest operations a computer can do. Easier than multiplication and even addition. And guess what? The TI-84+ can indeed perform this operation, but there's no way to do it in TI-BASIC. (Note that there is an "xor" command, but it's a logical xor, not bitwise.)

Anyway, there are two ways to do a bitwise xor using "normal" math. The first involves imaginary numbers and I'm convinced only a madman could have figured it out. I found the algorithm on an old Cemetech thread here: https://www.cemetech.net/forum/viewtopic.php?t=9905

:int(log(2)⁻¹log(max(A,B
:2^cumSum(binomcdf(Ans,0
:sum(Ans.5(1=abs(int(2fPart(Ans⁻¹(A+B𝑖

Weregoose, you are a madman. (Props to KermMartian too for refining it.) It took me a while to figure out what's going on mathematically (and I quickly lose my grasp on it after I stop thinking about it), but basically, the absolute value function can perform a pseudo-xor on complex numbers: abs(0) = 0; abs(1) = 1; abs(𝑖) = 1; abs(1+𝑖) = sqrt(2). (This is how I learned that the absolute value function is just the distance function in the complex plane!) If you treat the real and imaginary parts as two input bits, then you can "xor" them together by checking if the result equals 1 (and not 0 or sqrt(2)). Isn't this just a logical xor, though? Yes, but the trick here is that a single (complex) number can carry both inputs, which makes it all faster (I tested it). If you pre-cache the powers of 2 (what the binomcdf line generates), you can do about 3 xors a second. For reference, your average laptop can do several billion.

My good friend Claude came up with a faster method, but you have to precache a 256-element "nibble" table. (A nibble is half a byte.) It can then compute the xor of the 4 high bits and 4 low bits by looking them up in a table. It's about twice as fast, but more memory-intensive, and definitely not as cool. You can choose which algorithm you want to use in the options menu.

The funny thing is, none of this xor stuff is even really necessary in theory. It's all for generating the error-correcting codes, which is what makes QR codes resilient to damage, but that really only matters for printed QR codes that could get torn or dirty. Unfortunately, we can't skip generating the ECC, because most QR code scanners won't recognize it as a valid code without them.

WHO CARES?

Why would you potentially wait ten minutes for your calculator to generate a QR code that you're just going to scan with your phone?

Well, first of all, it's only 30 seconds for a small (version 1) code. But indeed, this QR code generator is closer to a speedrunning challenge -- a work of art, even -- than it is a practical program. Honestly, I just wanted to make a pure BASIC QR code generator to prove that it was possible, and, well, here it is. If you want actual functionality, I have a sister project where the encoding and drawing functions are written in assembly and it literally takes one second, and it even lets you load NoteFolio files as the input. It still uses a BASIC program as a wrapper with a similar interface.

ASCII MODE

The TI-83+ does support every ASCII character, though not all of them can be typed with the regular keys (like semicolon). Also note that the negative and minus signs are different (only the minus sign is valid ASCII). Oh yeah, and you also have to use π (pi) instead of quotation marks. You may be aware that, since the calculator has no escape metacharacter for strings, it's impossible to put a quotation mark in a string. (Or is it? You actually can do it if you manually enter quotation mark when prompted by the Input command within a program, or transfer the string directly to your calculator.) But since we can't set it programatically, I use the pi symbol in its place, since it's convenient to type.

However, if you want to fix the ASCII string yourself (I use Str3 as our alphabet: ASCII characters 32 to 126), I've created an option that tells the program not to overwrite Str3. You can even come up with an entirely new character set if you want. Note that if Str3 doesn't contain exactly 95 characters (perhaps because a different program did something with it), then you'll be back to the old ASCII-with-pi character set. Why does this need to be an option at all, you might ask? Isn't it safe enough to just do that length=95 check? In some world, I'm sure it is, but in ours, there's actually no way to check if a string is defined in TI-Basic without erroring out if it doesn't. Enabling this option really just tells the program to assume Str3 exists in some form.

If you select ASCII mode with non-ASCII characters (like the calculator-specific tokens such as "sin("), the program reports the first such character and its position.

ALPHANUMERIC MODE

Because the calculator uses all upper-case letters by default, I figured Alphanumeric would be the premier encoding mode, as it lets you use the 10 digits, 26 upper-case letters, a space, and 8 punctuation characters. What more could you want? The problem is, these punctuation appear to have been chosen for encoding URIs and other technical stuff, and aren't ideal for composing a message. They are (enclosed in quotation marks) "$%*+-./:". Dollar sign and percent? Really? Could I please have a question mark or even a comma?

To address this, I created my own set of punctuation optimized for natural English: "?;',-.!:". Three of these are the same (hyphen, period, colon) and the rest are positioned so they line up with the symbol that looks the most similar. If you enable this mode, you can use this alternate set of punctuation, although if you scan the code on your phone, they'll get mapped back to the standard symbols. Depending on what you want to do with the data, you can write your own program on the other end that translates these characters back to the "useful" ones, but that's up to you.

If you select Alphanumeric mode with illegal characters, the program reports the first such character and its position.

BINARY MODE

To use this mode, you must first store your binary data in list BIN (perhaps with the list editor) and then select Binary encoding. Unlike Alphanumeric and ASCII mode, Binary mode does not prompt you to input the data and assumes list BIN has already been set up. Note that only the lower 8 bits are used and the program won't warn you about values higher than 255.

REDRAW

Tells the program to draw a QR code based on whatever data exists in list CW (codewords). This can be useful if your QR code got erased but the data is still in memory. This is mostly just for testing purposes, though. Remember, you can turn on the "StorePic 1" option to automatically save the code when it finishes drawing.

LIMITATIONS

Because speed is the only thing that matters, we're not generating our QR codes in the recommended way. QR codes have four levels of error correction: Low, Medium, Quartile, and High. The higher you go, the more xors you have to do, so we don't even give you the option: this program is hard-coded for Low mode. Then there's the "masking" phase, where, after generating the codewords, the generator "tries on" eight different masks (basically different ways of displaying the code) and scores the results for readability using a complex algorithm that basically tries to minimize large clusters of all-white or all-black pixels, or things that look like alignment patterns. EFF THAT. That would be insane to try to implement on the calculator, so we just apply Mask 0 and say good enough. In theory this could generate codes that are a little difficult to scan, but remember: QR codes were invented in the 90s. Our technology is way better now, and we can get away with a lot before actually running into problems.

Truncation: if your message doesn't fit within the largest size we can draw (version 11), it will be truncated with a warning.

In an effort to save a few seconds when drawing, the code is drawn in the top-left corner of the screen. This shouldn't be a problem since the screen itself has a "quiet zone" around it, but it isn't ideal. Maybe I should add an option to make the code centered, but I haven't had any problems scanning it.

STATISTICS

Ver:   QR code version. Note that "version" in QR code context just refers to the size, as opposed to some previous standard. They are different "versions" in the sense that they may feature different layouts. Version 11 is 61x61 pixels and is the largest size that can be displayed on the calculator screen.
Size:  Number of pixels per side (all QR codes are square). Versions grow incrementally by 4 pixels.
Bin:   Max encodable bytes or ASCII chars
Alnum: Max encodable alphanumeric chars
ʟCW:   Finished length of the CW list (Useful for testing; for example, you can run randInt(0,255,405->CW and then run a redraw to test v11. Note that you won't get a valid, scannable QR code, though.)
Enc:   Time to build the codewords
ECC:   Time to calculate the error-correcting codes (This is the real bottleneck, where the xors are.)
Draw:  Time to draw the QR code to the graph (This part is the most optimized and I'd be surprised if anyone could meaningfully speed it up.)

| Ver | Size | Bin | Alnum | ʟCW | Enc |  ECC  | Draw  | TOTAL TIME | Char/sec |
|   1 |   21 |  17 |    25 |  27 |  3s |   14s |   13s |        30s | 0.83     |
|   2 |   25 |  32 |    47 |  45 |  5s |   29s |   20s |        54s | 0.87     |
|   3 |   29 |  53 |    77 |  71 |  9s | 1m02s |   31s |      1m42s | 0.75     |
|   4 |   33 |  78 |   114 | 101 | 12s | 1m51s |   43s |      2m42s | 0.70     |
|   5 |   37 | 106 |   154 | 135 | 17s | 3m07s |   57s | !!!  4m21s | 0.59     |
|   6 |   41 | 134 |   195 | 173 | 21s | 2m59s | 1m12s |      4m32s | 0.72     |
|   7 |   45 | 154 |   224 | 197 | 24s | 3m43s | 1m26s |      5m33s | 0.67     |
|   8 |   49 | 192 |   279 | 243 | 31s | 5m21s | 1m45s |      7m36s | 0.61     |
|   9 |   53 | 230 |   335 | 293 | 38s | 7m42s | 2m05s | !!! 10m25s | 0.54     |
|  10 |   57 | 271 |   395 | 347 | 46s | 6m05s | 2m25s |      9m16s | 0.71     |
|  11 |   61 | 321 |   468 | 405 | 55s | 7m49s | 2m49s |     11m33s | 0.68     |

Performance tests were done with a TI-84+ Silver Edition with relatively new batteries. (XOR table is enabled.)

Note that v9 is slower than v10! This is because v10 uses four relatively small ECC blocks, while v9 uses two larger ones with more xor operations in total. For this reason, we have a special check that always skips v9 unless chosen manually. v6 actually outperforms v5 during the ECC phase for a similar reason (it's where it jumps from one large block to two smaller ones), and with the XOR table turned off, the gap widens and v6 wins in total time. If you have the XOR table turned off, we'll skip v5 too.

Char/sec measures alphanumeric characters processed per second, for the purpose of some theoretical throughput. If you're ever in the position of having to send messages as fast a possible over QR codes generated with this program (sounds like hell), I guess stick to version 2.

TECHNICAL DETAILS

Here's what the program actually does:

1. Calculate the version based on the length of the input.
2. Encode the input into codepoints. If any characters are illegal, reject the input.
3. Create the codewords. This is the phase that calls θQRBIT, which packs the codepoints into ʟCW. For example, alphanumeric mode encodes two characters at a time into 11 bits, which have to be reorganized into 8-bit codewords. This part is fairly well optimized, given that we don't have true bitwise functions on the calculator. It may be possible to speed it up further, but probably not without a different paradigm.
4. Error correction. This is the hard part. Different versions use different quantities and sizes of ECC blocks. The size of these blocks determines which generator polynomial to use. Then, for each block, we use Reed-Solomon division to fill out the blocks. This is where we have to do a ton of bitwise xors and we lose all our time.
5. Interleaving. When there are multiple ECC blocks, they get interleaved. This part doesn't take too long, but it does require copying the codeword list, which is the most memory-intensive part.
6. Drawing. We draw the code pixel-by-pixel using only Pxl-On, meaning the graph's X/Y bounds don't matter. This is probably the most optimized part, and we have several tricks to save time. QR codes use a weird zig-zag system that wraps around the fixed patterns, so we fill those in completely first so we can use pxl-Test to avoid them. We also adjust the bounds in the drawing loop so we don't waste any time avoiding the finder patterns (the things in the corners). Finally, we "fix up" the fixed patterns by erasing the parts that we had to turn on for pxl-Test to see them.

Fun fact: originally, my solution to avoiding fixed patterns was to store an equation on a Y-Var that calculated whether a pixel was reserved or not. The equation got more complex at higher versions, and for v6 and up, it looked like this:
"I=6 or abs(TfPart(I/T)-6)<=2.1 and abs(TfPart(J/T)-6)<=2.1 and abs(I-J)<=S/2-2 or J>=S-11 and I<=5"
Pretty cool, right? Just plug in I and J (plus a value of T which changed with the version) and it will tell you if the pixel is reserved or not. (What's with the 2.1s? It just happened to be the right number to make the math work out!) The problem was, it was *slow*. We had to evaluate this equation for every single pixel before drawing, and drawing a v11 code took over 5 minutes.

MEMORY USAGE

It depends on how much text you're encoding, but you'll need about 5000 bytes free to fully build the codeword list for v11.

VARIABLES USED

This program uses almost all of the letter variables, all 6 built-in lists, and Strings 1, 2, and 3.

HAPPY SCANNING!
