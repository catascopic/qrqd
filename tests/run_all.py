"""Runs the test suites in parallel and prints one line per suite.

The pure-BASIC generator's test (test_basic.py, minutes even with --quick) is left out
unless --basic is given: it only needs running when src/QRBASIC.basic.txt or
src/_theta_QRBIT.basic.txt change.

  python tests/run_all.py            full engine sweeps, NoteFolio, front ends, tools
  python tests/run_all.py --quick    engine sweeps (and test_basic) on versions 1, 5, 10 only
  python tests/run_all.py --basic    also the pure-BASIC generator

Build first (python tools/build.py): the engine tests run the built Z80 engine
(build/_theta_QR.8xp, which needs spasm-ng), the front-end and BASIC tests the built files.
"""
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUICK = ['--quick'] if '--quick' in sys.argv else []
SUITES = [['test_engine.py'] + QUICK,                  # the release's engine, the Z80 one
          ['test_engine.py', '--axe'] + QUICK,         # frozen: the Axe engine
          ['test_engine.py', '--legacy'] + QUICK,      # frozen: the older set
          ['test_notefolio.py'],
          ['test_notefolio.py', '--axe'],
          ['test_legacy_notefolio.py'],
          ['test_frontend.py'],
          ['test_legacy_frontend.py'],
          ['test_lorem.py'],
          ['test_txt2note.py'],
          ['test_unprot.py'],
          ['test_codechat.py'],
          ['test_z80sim.py']]
if '--basic' in sys.argv:
    SUITES.append(['test_basic.py'] + QUICK)


def run(args):
    start = time.perf_counter()
    r = subprocess.run([sys.executable, str(HERE / args[0])] + args[1:], capture_output=True,
                       env={**os.environ, 'PYTHONUTF8': '1'}, encoding='utf-8', errors='replace')
    return args, r, time.perf_counter() - start


if __name__ == '__main__':
    failed = 0
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        for args, r, secs in pool.map(run, SUITES):
            ok = r.returncode == 0
            failed += not ok
            print('%-4s %-38s %6.1fs' % ('ok' if ok else 'FAIL', ' '.join(args), secs))
            if not ok:   # the suite's own failure lines, or the end of a traceback
                lines = [l for l in (r.stdout + r.stderr).splitlines() if not l.startswith('ok ')]
                print('\n'.join('     ' + l for l in lines[-15:]))
    print('\nALL PASSED' if not failed else '\n%d SUITE(S) FAILED' % failed)
    sys.exit(1 if failed else 0)
