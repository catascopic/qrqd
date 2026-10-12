"""Tiny interpreter for the subset of Axe used by QRSRC.txt.

Models: strict left-to-right evaluation, 16-bit unsigned math, byte/word
memory, OS variable lookup via GetCalc, float{}, the main and back graph
buffers, subroutine calls with r1..r6 arguments.  Anything whose behaviour
on a real calculator is uncertain raises an error instead of guessing.

The note picker's commands are modelled loosely: Text( records (x, y, string)
instead of drawing glyphs (there is no font), Rect( fills and RectI( inverts a rectangle
(on either buffer), getKey returns scripted keys (running out raises, so a stuck loop
can't hang a test),
and returning with Fix 5 or Fix 7 still on is an error. The home screen is a
16x8 grid of character codes (`home`): Output( moves the cursor (curCol 844Ch,
curRow 844Bh), Disp X►Char writes one cell and advances, DispGraph wipes it.
Asm( runs only the OS calls listed in ASM (anything else raises).
"""
import re

L1, L3, L6 = 0x86EC, 0x9872, 0x9340
TWO_BYTE = {0x5C, 0x5D, 0x5E, 0x60, 0x61, 0x62, 0x63, 0x7E, 0xAA, 0xBB, 0xEF}

TOKENS = [  # longest first matters
    'float{', 'GetCalc(', 'inData(', 'pxl-Test(', 'Pxl-On(', 'Copy(', 'Buff(',
    'Text(', 'RectI(', 'Rect(', 'Fix ', 'getKey', 'Output(', '►Char', 'Asm(',
    'sub(', '!If ', 'If ', 'Else', 'End', 'While ', 'For(', 'Return', 'Lbl ',
    'ClrDraw', 'DispGraph', 'Disp ', 'Full', 'Ans', ' and ', ' or ', ' xor ',
    'Y₁', 'L₁', 'L₂', 'L₃', 'L₄', 'L₅', 'L₆', 'r₁', 'r₂', 'r₃', 'r₄', 'r₅', 'r₆',
    '→', 'ʳ', '≠', '≤', '≥', '·', '+', '-', '*', '/', '^', '=', '<', '>',
    '(', ')', '{', '}', ',',
]
BINOPS = {'+', '-', '*', '/', '^', '=', '≠', '<', '>', '≤', '≥',
          ' and ', ' or ', ' xor ', '·'}


ASM = {'EF7045': 'RunIndicOff'}   # bcall _RunIndicOff


class AxeError(Exception):
    pass


def lex(line):
    out, i = [], 0
    while i < len(line):
        if line[i] == '"':
            j = line.index('"', i + 1)
            out.append(('STR', line[i + 1:j])); i = j + 1; continue
        if line[i] == '[':
            j = line.index(']', i)
            out.append(('HEX', line[i + 1:j])); i = j + 1; continue
        if line[i] == 'ᴇ':
            j = i + 1
            while j < len(line) and line[j] in '0123456789ABCDEF':
                j += 1
            out.append(('NUM', int(line[i + 1:j], 16))); i = j; continue
        m = re.match(r'GDB\d', line[i:])
        if m:
            out.append(('CONST', m.group())); i += 4; continue
        for t in TOKENS:
            if line.startswith(t, i):
                out.append(('T', t)); i += len(t); break
        else:
            c = line[i]
            if c.isdigit():
                j = i
                while j < len(line) and line[j].isdigit():
                    j += 1
                out.append(('NUM', int(line[i:j]))); i = j
            elif c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZθ':
                out.append(('VAR', c)); i += 1
            else:
                raise AxeError('cannot lex %r in %r' % (line[i:], line))
    return out


class Machine:
    def __init__(self, src):
        self.mem = bytearray(65536)
        self.vars = {}
        self.ans = None
        self.static = {}
        self.data_ptr = 0xA000
        self.os = {}          # name -> pointer to data
        self.os_ptr = 0xC000
        self.displays = []
        self.shown = []       # strings from Disp (home screen)
        self.free_ram = 12000 # bytes GetCalc(name,SIZE) may create before returning 0
        self.literals = {}
        self.appvars = {}     # name -> (pointer to data, archived?)
        self.file = None      # data pointer of the open Y1 file
        self.arch_ptr = 0x4000
        self.vat = []
        self.keys = []        # scripted getKey results
        self.texts = []       # (x, y, string) drawn since the last ClrDraw
        self.rects = []       # inverted rectangles since the last ClrDraw
        self.frames = []      # (texts, rects) at each DispGraph
        self.fix = 4          # 4 text to the screen, 5 to the buffer
        self.scroll = 6       # 6 scroll at the last line, 7 don't
        self.home = {}        # (col, row) -> character code on the home screen
        self.run_indicator = True
        self.lines = []
        for raw in src.split('\n'):
            s = raw.rstrip('\n')
            if not s.strip() or s.startswith('.'):
                continue
            self.lines.append(s)
        self.parse()

    # ---------- OS variables ----------
    def _alloc(self, data):
        p = self.os_ptr
        self.mem[p:p + len(data)] = data
        self.os_ptr += len(data) + 16
        return p

    @staticmethod
    def tifloat(n):
        if n == 0:
            return bytes([0, 0x80] + [0] * 7)
        neg = n < 0
        d = str(abs(int(n)))
        exp = len(d) - 1
        d = (d + '0' * 14)[:14]
        mant = bytes(int(d[k]) * 16 + int(d[k + 1]) for k in range(0, 14, 2))
        return bytes([0x80 if neg else 0, 0x80 + exp]) + mant

    @staticmethod
    def untifloat(b):
        exp = b[1] - 0x80
        digits = ''.join('%d%d' % (x >> 4, x & 15) for x in b[2:9])
        if b[1] == 0x80 and int(digits) == 0:
            return 0
        val = int(digits[:exp + 1]) if exp >= 0 else 0
        if b[0] & 0x80:
            raise AxeError('negative float')
        return val

    def set_real(self, name, v):
        self.os[('real', name)] = self._alloc(self.tifloat(v))

    def get_real(self, name):
        p = self.os[('real', name)]
        return self.untifloat(self.mem[p:p + 9])

    def set_str(self, n, toks):
        data = bytes(toks)
        p = self._alloc(len(data).to_bytes(2, 'little') + data)
        self.os[('str', n)] = p + 2

    def set_list(self, name, values):
        data = len(values).to_bytes(2, 'little') + b''.join(self.tifloat(v) for v in values)
        p = self._alloc(data)
        self.os[('list', name)] = p + 2

    def add_appvar(self, name, content, archived=False):
        blob = len(content).to_bytes(2, 'little') + bytes(content)
        if archived:   # flash: readable, not writable (wr() refuses < 0x8000)
            p = self.arch_ptr
            self.mem[p:p + len(blob)] = blob
            self.arch_ptr += len(blob) + 32
        else:
            p = self._alloc(blob)
        self.appvars[name] = (p + 2, archived)
        self.vat.append((0x15, name, archived))

    def add_vat_other(self, typ, name):
        self.vat.append((typ, name, False))

    def build_vat(self):
        top = 0xF800
        p = top
        for typ, name, archived in self.vat:
            nb = name.encode('latin-1')
            self.mem[p] = typ
            self.mem[p - 1] = 0
            self.mem[p - 2] = 0
            self.mem[p - 3] = 0x34; self.mem[p - 4] = 0x12   # DAL/DAH (unused)
            self.mem[p - 5] = 1 if archived else 0
            self.mem[p - 6] = len(nb)
            for k, ch in enumerate(nb):
                self.mem[p - 7 - k] = ch
            p -= 7 + len(nb)
        self.mem[0x9830:0x9832] = top.to_bytes(2, 'little')   # progPtr
        self.mem[0x982E:0x9830] = p.to_bytes(2, 'little')     # pTemp

    def appvar_create(self, name, size):
        """GetCalc("appvNAME",SIZE): 0 if there isn't enough RAM; replaces an existing one."""
        if size > self.free_ram:
            return 0
        self.free_ram -= size
        p = self._alloc(size.to_bytes(2, 'little') + bytes(size))
        self.appvars[name] = (p + 2, False)
        return p + 2

    def str_create(self, n, size):
        p = self._alloc(size.to_bytes(2, 'little') + bytes(size))
        self.os[('str', n)] = p + 2
        return p + 2

    def getcalc_str(self, s):
        if s.startswith('var') and len(s) == 4:
            return self.os.get(('real', s[3]), 0)
        m = re.fullmatch(r'Str(\d)', s)
        if m:
            return self.os.get(('str', int(m.group(1))), 0)
        raise AxeError('unknown GetCalc string ' + s)

    def getcalc_ptr(self, p):
        b = self.mem[p:p + 9]
        typ = b[0]
        if typ == 0x00:                      # real variable, e.g. "varN"
            return self.os.get(('real', chr(b[1])), 0)
        if typ == 0x01 and b[1] == 0x5D:
            name = bytes(b[2:]).split(b'\0')[0].decode()
            return self.os.get(('list', name), 0)
        if typ == 0x15:
            name = bytes(b[1:]).split(b'\0')[0].decode('latin-1')
            ptr, archived = self.appvars.get(name, (0, False))
            return 0 if archived else ptr
        raise AxeError('unsupported OP1 name %s' % b.hex())

    # ---------- parsing ----------
    def parse(self):
        self.stmts = []
        self.labels = {}
        for s in self.lines:
            self.stmts.append(lex(s))
        stack = []
        self.match = {}
        for i, t in enumerate(self.stmts):
            h = t[0]
            if h == ('T', 'Lbl '):
                self.labels[''.join(x[1] for x in t[1:])] = i
            elif h in [('T', 'If '), ('T', '!If '), ('T', 'While '), ('T', 'For(')]:
                stack.append(i)
            elif h == ('T', 'Else') and len(t) == 1:
                self.match[stack[-1], 'else'] = i
                self.match[i] = stack[-1]
            elif h == ('T', 'End') and len(t) == 1:
                o = stack.pop()
                self.match[o] = i
                self.match[i, 'open'] = o
        if stack:
            raise AxeError('unclosed block at %s' % self.lines[stack[-1]])

    # ---------- memory ----------
    def rd(self, p):
        return self.mem[p & 0xFFFF]

    def rd16(self, p):
        return self.mem[p & 0xFFFF] | self.mem[(p + 1) & 0xFFFF] << 8

    def wr(self, p, v):
        p &= 0xFFFF
        if p < 0x8000:
            raise AxeError('write to ROM %04x' % p)
        self.mem[p] = v & 0xFF

    def wr16(self, p, v):
        self.wr(p, v); self.wr(p + 1, v >> 8)

    def pix(self, x, y, back, test=False):
        if not (0 <= x < 96 and 0 <= y < 64):
            raise AxeError('pixel out of range %d,%d' % (x, y))
        base = L3 if back else L6
        a = base + y * 12 + x // 8
        bit = 0x80 >> (x % 8)
        if test:
            return 1 if self.mem[a] & bit else 0
        self.mem[a] |= bit

    # ---------- expressions ----------
    def expr(self, toks, i):
        v, i = self.operand(toks, i)
        while i < len(toks) and toks[i][0] == 'T' and toks[i][1] in BINOPS:
            op = toks[i][1]
            w, i = self.operand(toks, i + 1)
            v = self.binop(op, v, w)
        return v, i

    def binop(self, op, a, b):
        if op in (' and ', ' or ', ' xor '):
            if a > 255 or b > 255:
                raise AxeError('8-bit op on value > 255: %d %s %d' % (a, op, b))
            r = {' and ': a & b, ' or ': a | b, ' xor ': a ^ b}[op]
        elif op == '+': r = a + b
        elif op == '-': r = a - b
        elif op == '*': r = a * b
        elif op == '/':
            if b == 0: raise AxeError('div by 0')
            r = a // b
        elif op == '^':
            if b == 0: raise AxeError('mod by 0')
            r = a % b
        elif op == '·': r = a & b
        elif op == '=': r = int(a == b)
        elif op == '≠': r = int(a != b)
        elif op == '<': r = int(a < b)
        elif op == '>': r = int(a > b)
        elif op == '≤': r = int(a <= b)
        elif op == '≥': r = int(a >= b)
        return r & 0xFFFF

    def expect(self, toks, i, t):
        if i >= len(toks) or toks[i] != ('T', t):
            raise AxeError('expected %r at %d in %r' % (t, i, toks))
        return i + 1

    def operand(self, toks, i):
        k, t = toks[i]
        if k == 'NUM': return t & 0xFFFF, i + 1
        if k == 'VAR': return self.vars.get(t, 0), i + 1
        if k == 'CONST': return self.static[t], i + 1
        if t in ('L₁', 'L₃', 'L₆'): return {'L₁': L1, 'L₃': L3, 'L₆': L6}[t], i + 1
        if t.startswith('r') and len(t) == 2: return self.vars.get(t, 0), i + 1
        if t == '(':
            v, i = self.expr(toks, i + 1)
            return v, self.expect(toks, i, ')')
        if t == '{':
            p, i = self.expr(toks, i + 1)
            i = self.expect(toks, i, '}')
            if i < len(toks) and toks[i] == ('T', 'ʳ'):
                return self.rd16(p), i + 1
            return self.rd(p), i
        if t == 'float{':
            p, i = self.expr(toks, i + 1)
            i = self.expect(toks, i, '}')
            if p == 0: raise AxeError('float{0}')
            return self.untifloat(self.mem[p:p + 9]) & 0xFFFF, i
        if t == 'GetCalc(':
            if toks[i + 1][0] == 'STR':
                name = toks[i + 1][1]; i += 2
                if toks[i] == ('T', ','):
                    size, i = self.expr(toks, i + 1)
                    if name.startswith('appv'):
                        v = self.appvar_create(name[4:], size)
                    else:
                        m = re.fullmatch(r'Str(\d)', name)
                        v = self.str_create(int(m.group(1)), size)
                else:
                    v = self.getcalc_str(name)
            else:
                p, i = self.expr(toks, i + 1)
                if toks[i] == ('T', ','):
                    assert toks[i + 1] == ('T', 'Y₁'), 'only Y1 files supported'
                    i += 2
                    b = self.mem[p:p + 9]
                    assert b[0] == 0x15
                    name = bytes(b[1:]).split(b'\0')[0].decode('latin-1')
                    if name in self.appvars:
                        self.file = self.appvars[name][0]; v = 1
                    else:
                        self.file = None; v = 0
                else:
                    v = self.getcalc_ptr(p)
            return v, self.expect(toks, i, ')')
        if k == 'STR':             # string literal: zero-terminated static data
            if t not in self.literals:
                self.literals[t] = self.data_ptr
                data = t.encode('ascii') + bytes(1)
                if t.startswith('var') and len(t) == 4:   # Axe stores "varA" as an OS name
                    data = bytes([0x00, ord(t[3])]) + bytes(7)
                self.mem[self.data_ptr:self.data_ptr + len(data)] = data
                self.data_ptr += len(data)
            return self.literals[t], i + 1
        if t == 'getKey':
            if not self.keys: raise AxeError('getKey: no scripted keys left')
            return self.keys.pop(0), i + 1
        if t == 'Y₁':
            if self.file is None: raise AxeError('Y1 used without an open file')
            return self.file, i + 1
        if t == 'inData(':
            b, i = self.expr(toks, i + 1)
            i = self.expect(toks, i, ',')
            p, i = self.expr(toks, i)
            if b > 255: raise AxeError('inData byte %d' % b)
            if toks[i] == ('T', ','):        # inData(BYTE,PTR,SIZE): search SIZE bytes
                size, i = self.expr(toks, i + 1)
                i = self.expect(toks, i, ')')
                if b == 0: raise AxeError('inData byte 0 with a size')
                data = self.mem[p:p + size]
                return (data.index(b) + 1 if b in data else 0), i
            i = self.expect(toks, i, ')')
            if b == 0: return 0, i           # "The byte 0 will never be found" (Axe docs)
            n = 1
            while self.mem[p]:
                if self.mem[p] == b: return n, i
                p += 1; n += 1
            return 0, i
        if t == 'pxl-Test(':
            x, i = self.expr(toks, i + 1)
            i = self.expect(toks, i, ',')
            y, i = self.expr(toks, i)
            i = self.expect(toks, i, ')')
            back = i < len(toks) and toks[i] == ('T', 'ʳ')
            return self.pix(x, y, back, test=True), i + (1 if back else 0)
        raise AxeError('bad operand %r' % (toks[i:],))

    # ---------- execution ----------
    def run(self, max_steps=50_000_000):
        pc, calls, steps = 0, [], 0
        forinfo = {}
        while True:
            steps += 1
            if steps > max_steps: raise AxeError('too many steps')
            if pc >= len(self.stmts):
                raise AxeError('fell off end of program')
            t = self.stmts[pc]
            h = t[0]
            if h == ('T', 'Lbl '):
                raise AxeError('fell into a label at %s' % self.lines[pc])
            if h in [('T', 'If '), ('T', '!If ')]:
                v, j = self.expr(t, 1)
                assert j == len(t), self.lines[pc]
                cond = (v != 0) if h[1] == 'If ' else (v == 0)
                if cond: pc += 1
                else:
                    e = self.match.get((pc, 'else'))
                    pc = (e + 1) if e is not None else self.match[pc] + 1
                continue
            if h == ('T', 'Else') and len(t) == 1:
                pc = self.match[self.match[pc]] + 1; continue
            if h == ('T', 'While '):
                v, j = self.expr(t, 1)
                assert j == len(t)
                pc = pc + 1 if v else self.match[pc] + 1
                continue
            if h == ('T', 'For('):
                var = t[1][1]
                j = self.expect(t, 2, ',')
                a, j = self.expr(t, j)
                j = self.expect(t, j, ',')
                b, j = self.expr(t, j)
                j = self.expect(t, j, ')')
                assert j == len(t)
                if a > b: raise AxeError('empty For loop at ' + self.lines[pc])
                self.vars[var] = a
                forinfo[pc] = (var, b)
                pc += 1; continue
            if h == ('T', 'End') and len(t) == 1:
                o = self.match[pc, 'open']
                oh = self.stmts[o][0]
                if oh == ('T', 'While '):
                    pc = o; continue
                if oh == ('T', 'For('):
                    var, b = forinfo[o]
                    self.vars[var] = (self.vars[var] + 1) & 0xFFFF
                    pc = o + 1 if self.vars[var] <= b else pc + 1
                    continue
                pc += 1; continue
            if h == ('T', 'Return'):
                if not calls:
                    if self.fix == 5: raise AxeError('returned with Fix 5 on')
                    if self.scroll == 7: raise AxeError('returned with Fix 7 on')
                    return
                pc = calls.pop(); continue
            if h == ('T', 'sub('):
                name = ''
                j = 1
                while t[j][0] == 'VAR': name += t[j][1]; j += 1
                args = []
                while t[j] == ('T', ','):
                    v, j = self.expr(t, j + 1); args.append(v)
                self.expect(t, j, ')')
                for k, v in enumerate(args):
                    self.vars['r' + '₁₂₃₄₅₆'[k]] = v
                calls.append(pc + 1)
                pc = self.labels[name] + 1; continue
            if h == ('T', 'Pxl-On('):
                x, j = self.expr(t, 1)
                j = self.expect(t, j, ',')
                y, j = self.expr(t, j)
                j = self.expect(t, j, ')')
                back = j < len(t) and t[j] == ('T', 'ʳ')
                self.pix(x, y, back)
                pc += 1; continue
            if h == ('T', 'ClrDraw'):
                base = L3 if len(t) > 1 and t[1] == ('T', 'ʳ') else L6
                self.mem[base:base + 768] = bytes(768)
                if base == L6: self.texts, self.rects = [], []
                pc += 1; continue
            if h == ('T', 'Disp ') and t[-1] == ('T', '►Char'):
                c, j = self.expr(t, 1)
                assert j == len(t) - 1, self.lines[pc]
                col, row = self.mem[0x844C], self.mem[0x844B]
                if not (col < 16 and row < 8): raise AxeError('cursor at %d,%d' % (col, row))
                self.home[col, row] = c & 0xFF
                col += 1
                if col == 16:
                    col, row = 0, row + 1
                    if row == 8:
                        if self.scroll == 6: raise AxeError('Disp scrolled the home screen')
                        row = 7
                self.mem[0x844C], self.mem[0x844B] = col, row
                pc += 1; continue
            if h == ('T', 'Asm('):
                code = ''.join(str(x[1]) if x[0] in ('NUM', 'VAR') else '' for x in t[1:-1])
                assert t[-1] == ('T', ')') and all(x[0] in ('NUM', 'VAR') for x in t[1:-1]), self.lines[pc]
                if ASM.get(code) != 'RunIndicOff': raise AxeError('unmodelled Asm(%s)' % code)
                self.run_indicator = False
                pc += 1; continue
            if h == ('T', 'Output('):
                x, j = self.expr(t, 1); j = self.expect(t, j, ',')
                y, j = self.expr(t, j); j = self.expect(t, j, ')')
                assert j == len(t), self.lines[pc]
                if not (x < 16 and y < 8): raise AxeError('Output(%d,%d' % (x, y))
                self.mem[0x844C], self.mem[0x844B] = x, y
                pc += 1; continue
            if h == ('T', 'Disp '):
                p, j = self.expr(t, 1)
                assert j == len(t), self.lines[pc]
                self.shown.append(bytes(self.mem[p:self.mem.index(0, p)]).decode('latin-1'))
                pc += 1; continue
            if h == ('T', 'Full'):           # CPU speed only; nothing to simulate
                assert len(t) == 1, self.lines[pc]
                self.full = True; pc += 1; continue
            if h == ('T', 'DispGraph'):
                self.displays.append(bytes(self.mem[L6:L6 + 768]))
                self.frames.append((list(self.texts), list(self.rects)))
                self.home = {}
                pc += 1; continue
            if h == ('T', 'Fix '):
                assert t[1][0] == 'NUM' and len(t) == 2
                n = t[1][1]
                if n in (4, 5): self.fix = n
                elif n in (6, 7): self.scroll = n
                else: raise AxeError('unmodelled Fix %d' % n)
                pc += 1; continue
            if h == ('T', 'Text('):
                x, j = self.expr(t, 1); j = self.expect(t, j, ',')
                y, j = self.expr(t, j); j = self.expect(t, j, ',')
                p, j = self.expr(t, j); self.expect(t, j, ')')
                if self.fix != 5: raise AxeError('Text( without Fix 5 draws to the screen')
                text = bytes(self.mem[p:self.mem.index(0, p)]).decode('latin-1')
                if not (0 <= x < 96 and 0 <= y <= 58): raise AxeError('text at %d,%d' % (x, y))
                self.texts.append((x, y, text)); pc += 1; continue
            if h in (('T', 'RectI('), ('T', 'Rect(')):   # filled (Rect) or inverted (RectI)
                args, j = [], 1
                for k in range(4):
                    v, j = self.expr(t, j); args.append(v)
                    j = self.expect(t, j, ',' if k < 3 else ')')
                back = j < len(t) and t[j] == ('T', 'ʳ')
                base = L3 if back else L6
                x, y, w, hh = args
                if not (w and hh): raise AxeError('empty %s%d,%d' % (h[1], w, hh))
                for yy in range(y, y + hh):
                    for xx in range(x, x + w):
                        if not (0 <= xx < 96 and 0 <= yy < 64):
                            raise AxeError('%s out of range %d,%d' % (h[1], xx, yy))
                        bit = 0x80 >> (xx % 8)
                        if h[1] == 'RectI(':
                            self.mem[base + yy * 12 + xx // 8] ^= bit
                        else:
                            self.mem[base + yy * 12 + xx // 8] |= bit
                if h[1] == 'RectI(' and not back:
                    self.rects.append(tuple(args))
                pc += 1; continue
            if h == ('T', 'Copy('):
                s, j = self.expr(t, 1); j = self.expect(t, j, ',')
                d, j = self.expr(t, j); j = self.expect(t, j, ',')
                n, j = self.expr(t, j); self.expect(t, j, ')')
                for k in range(n):           # LDIR: forward byte copy
                    self.wr(d + k, self.mem[s + k])
                pc += 1; continue
            if h[0] == 'HEX':
                assert t[1] == ('T', '→') and t[2][0] == 'CONST'
                data = bytes.fromhex(h[1])
                self.static[t[2][1]] = self.data_ptr
                self.mem[self.data_ptr:self.data_ptr + len(data)] = data
                self.data_ptr += len(data)
                pc += 1; continue
            if h == ('T', 'Buff('):
                n = t[1][1]
                assert t[2] == ('T', ')') and t[3] == ('T', '→')
                self.static[t[4][1]] = self.data_ptr
                self.data_ptr += n
                pc += 1; continue
            # assignment
            v, j = self.expr(t, 0)
            j = self.expect(t, j, '→')
            k, x = t[j]
            if k == 'VAR' or x in ('r₁', 'r₂', 'r₃', 'r₄', 'r₅', 'r₆'):
                self.vars[x] = v; assert j + 1 == len(t)
            elif x == 'Ans':
                self.ans = v; assert j + 1 == len(t)
            elif x == 'float{':
                p, j2 = self.expr(t, j + 1)
                assert t[j2] == ('T', '}') and j2 + 1 == len(t), self.lines[pc]
                if p == 0: raise AxeError('→float{0}')
                for n, b in enumerate(self.tifloat(v)):
                    self.wr(p + n, b)
            elif x == '{':
                p, j2 = self.expr(t, j + 1)
                j2 = self.expect(t, j2, '}')
                if j2 < len(t) and t[j2] == ('T', 'ʳ'):
                    self.wr16(p, v); j2 += 1
                else:
                    self.wr(p, v)
                assert j2 == len(t), self.lines[pc]
            else:
                raise AxeError('bad store in ' + self.lines[pc])
            pc += 1
