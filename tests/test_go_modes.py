"""Regression test for the `go` handling - the three ways a caller can ask for a
move, plus the malformed one.  Each must finish on its own (except the bare `go`,
which by design waits for `stop`)."""
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'binaries', 'samodiva.exe')
INFO = re.compile(r'^info depth (\d+) multipv')
WATCH = re.compile(r'searching until `stop`')


def wd(p, s=25):
    threading.Thread(target=lambda: (time.sleep(s), p.poll() is None and p.kill()), daemon=True).start()


def start():
    p = subprocess.Popen([EXE], cwd=os.path.dirname(EXE),
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, bufsize=1)
    wd(p)
    p.stdin.write('setoption name Threads value 1\nsetoption name Hash value 32\n')
    p.stdin.write('position startpos\n')
    p.stdin.flush()
    return p


def collect(p, seconds, send_stop_after=None):
    lines = []
    t0 = time.time()
    sent = False
    while time.time() - t0 < seconds:
        l = p.stdout.readline()
        if not l:
            break
        l = l.strip()
        lines.append(l)
        if l.startswith('bestmove'):
            break
        if send_stop_after and not sent and time.time() - t0 > send_stop_after:
            p.stdin.write('stop\n'); p.stdin.flush()
            sent = True
    return lines


def done(p):
    try:
        p.stdin.write('quit\n'); p.stdin.flush(); p.wait(timeout=5)
    except Exception:
        p.kill()


print('1) go depth 12  -> must finish by itself, no "searching until stop" message')
p = start(); p.stdin.write('go depth 12\n'); p.stdin.flush()
L = collect(p, 20); done(p)
bm = [x for x in L if x.startswith('bestmove')]
warn = [x for x in L if WATCH.search(x)]
dep = [x for x in L if x.startswith('info depth')]
print('   bestmove: %-22s depths reported: %-4s guard message: %s'
      % (bm[0] if bm else 'NONE', len(dep), 'present <<< BUG' if warn else 'none'))
print('   -> %s' % ('OK' if bm and dep and not warn else 'FAIL'))

print()
print('2) go movetime 300 -> must finish by itself')
p = start(); p.stdin.write('go movetime 300\n'); p.stdin.flush()
L = collect(p, 20); done(p)
bm = [x for x in L if x.startswith('bestmove')]
warn = [x for x in L if WATCH.search(x)]
print('   bestmove: %-22s guard message: %s' % (bm[0] if bm else 'NONE', 'present <<< BUG' if warn else 'none'))
print('   -> %s' % ('OK' if bm and not warn else 'FAIL'))

print()
print('3) go wtime/btime -> must finish by itself')
p = start(); p.stdin.write('go wtime 3000 btime 3000\n'); p.stdin.flush()
L = collect(p, 20); done(p)
bm = [x for x in L if x.startswith('bestmove')]
warn = [x for x in L if WATCH.search(x)]
print('   bestmove: %-22s guard message: %s' % (bm[0] if bm else 'NONE', 'present <<< BUG' if warn else 'none'))
print('   -> %s' % ('OK' if bm and not warn else 'FAIL'))

print()
print('4) go nodes 200000 -> must finish by itself')
p = start(); p.stdin.write('go nodes 200000\n'); p.stdin.flush()
L = collect(p, 20); done(p)
bm = [x for x in L if x.startswith('bestmove')]
warn = [x for x in L if WATCH.search(x)]
print('   bestmove: %-22s guard message: %s' % (bm[0] if bm else 'NONE', 'present <<< BUG' if warn else 'none'))
print('   -> %s' % ('OK' if bm and not warn else 'FAIL'))

print()
print('5) go infinite -> must say so and answer on `stop`')
p = start(); p.stdin.write('go infinite\n'); p.stdin.flush()
L = collect(p, 15, send_stop_after=2.0); done(p)
bm = [x for x in L if x.startswith('bestmove')]
print('   after `stop`: %s' % (bm[0] if bm else 'NONE'))
print('   -> %s' % ('OK' if bm else 'FAIL'))

print()
print('6) bare go -> must say so and answer on `stop` (this is the fix)')
p = start(); p.stdin.write('go\n'); p.stdin.flush()
L = collect(p, 15, send_stop_after=2.0); done(p)
bm = [x for x in L if x.startswith('bestmove')]
w = [x for x in L if WATCH.search(x)]
print('   engine said: %s' % (w[0] if w else 'NOTHING <<< BUG'))
print('   after `stop`: %s' % (bm[0] if bm else 'NONE'))
print('   -> %s' % ('OK' if bm and w else 'FAIL'))
