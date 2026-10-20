"""Tests for the Z80 harness itself (tools/z80sim.py): tiny hand-assembled programs that do
one thing each, right or wrong. Each mistake must raise, so a bug in the assembly engine
can't pass the engine tests by doing something a calculator wouldn't survive.

  python tests/test_z80sim.py
"""
import sys

from qrtest import ROOT                          # noqa: F401 (puts tools/ on the path)
from z80sim import AsmMachine, Z80Error

HEAD = b'\xbb\x6d'
STO_ANS_0 = bytes.fromhex('efbf41' 'efbf4a')    # bcall(_OP1Set0) : bcall(_StoAns)
RET = b'\xc9'

failures = []


def expect(name, cond, detail=''):
    print(('ok    ' if cond else 'FAIL  ') + name + ('' if cond else '  ' + str(detail)))
    if not cond:
        failures.append(name)


def run(code, **kw):
    m = AsmMachine(HEAD + bytes.fromhex(code) if isinstance(code, str) else HEAD + code, **kw)
    m.run()
    return m


def fails(name, code, words, **kw):
    """The program must raise a Z80Error whose message contains `words`."""
    try:
        run(code, **kw)
        expect(name, False, 'no error')
    except Z80Error as e:
        expect(name, words in str(e), e)


if __name__ == '__main__':
    m = run(STO_ANS_0 + RET)
    expect('Ans = 0 through _OP1Set0 and _StoAns', m.ans == 0 and m.calls == ['_OP1Set0', '_StoAns'])
    m = run('3e01' '32ec86' '324093' '327298' 'c5c1' + STO_ANS_0.hex() + 'c9')
    expect('writes to L1, the graph buffer, L3 and the stack are allowed', m.ans == 0)
    m = run('db02' 'c9', model='83+')
    expect('port 2 can be read on a TI-83+', m.ans is None)
    m = run('3e01d320' 'c9')
    expect('15 MHz on a TI-84+ sets full', m.full)

    fails('a write to ROM raises', '320010' 'c9', 'write')
    fails("a write to the OS's RAM raises", '320080' 'c9', 'write')
    fails("overwriting the caller's return address raises", '210000' '22deff' 'c9', 'write')
    fails('an unknown bcall raises', 'ef0040' 'c9', 'unknown bcall')
    fails('returning with the stack off raises', '214000' 'e5' 'c9', 'stack')
    fails('changing IY raises', 'fd23' 'c9', 'IY')
    fails('returning with interrupts off raises', 'f3' 'c9', 'interrupts')
    fails('a jump into ROM raises', 'c30020', 'ROM')
    fails('a ret with a value left on the stack (into ROM) raises', 'c5' 'c9', 'ROM')
    fails('a hang is stopped', '18fe', 'still running', max_ticks=100_000)
    fails('an unknown port raises', 'db01' 'c9', 'port 01h')
    fails('the speed port on a TI-83+ raises', '3e01d320' 'c9', 'port 20h', model='83+')
    try:
        AsmMachine(b'\x3a' + RET)
        expect('a program without BB 6D is refused', False)
    except Z80Error:
        expect('a program without BB 6D is refused', True)

    print('\n%s' % ('ALL PASSED' if not failures else '%d FAILED' % len(failures)))
    sys.exit(1 if failures else 0)
