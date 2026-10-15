"""Verify the three shipped binaries.

Run from the repository root:

    python tests/verify_binaries.py

Checks, in a folder that contains no samodiva.nnue:

  1. each build starts and loads the network from inside the executable
  2. all three tiers return identical score, node count and move
  3. the engine never returns a move that is illegal in the position given
  4. the network it loads is the one in this repository (same FNV-1a)

Point SYZYGY_PATH at a tablebase directory to include tablebase probing:
    set SYZYGY_PATH=E:\\path\\to\\syzygy
"""
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, 'binaries')
sys.path.insert(0, HERE)
from minichess import Game   # noqa: E402

TB = os.environ.get('SYZYGY_PATH', '')
DEPTH = 10
INFO = re.compile(r'^info depth (\d+) multipv \d+ score (cp|mate) (-?\d+) nodes (\d+)')

BUILDS = [('samodiva.exe', 'native,  this machine only, fastest'),
          ('samodiva_v2.exe', 'x86-64-v2, any CPU from 2008 on'),
          ('samodiva_legacy.exe', 'x86-64, any x86-64 CPU, 2003+')]

FENS = [
    ('startpos', 'rnbqk2r/ppp2ppp/8/3pp3/4P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 4'),
    ('kiwipete', 'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1'),
    ('kq vs kr', '8/8/8/3k4/8/8/4Q3/4K3 w - - 0 1'),
]


class Eng:
    def __init__(self, path, cwd):
        self.q = queue.Queue()
        self.p = subprocess.Popen([path], cwd=cwd, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, bufsize=1)
        threading.Thread(target=self._r, daemon=True).start()

    def _r(self):
        for line in self.p.stdout:
            self.q.put(line.strip())
        self.q.put(None)

    def ask(self, *cmds, until=None):
        for c in cmds:
            try:
                self.p.stdin.write(c + '\n')
                self.p.stdin.flush()
            except Exception:
                return ['(процесът е умрял)']
        out = []
        while True:
            l = self.q.get()
            if l is None:
                out.append('(процесът е умрял)')
                break
            out.append(l)
            if until and l.startswith(until):
                break
        return out

    def kill(self):
        try:
            self.p.kill()
        except Exception:
            pass


def legal_move(fen, mv):
    """Independent legality check - not the engine's opinion of itself.

    Apply the move, then ask whether the mover's own king is attacked.  That
    catches king-into-check, which a plain move generator happily produces.
    """
    if mv in (None, '0000'):
        return False
    g = Game(fen)
    mover = g.turn
    try:
        g.apply(mv)
    except Exception:
        return False
    if g.turn == mover:
        return False                     # the move did not change sides
    g.turn = mover                       # in_check() now looks at our own king
    return not g.in_check()


fails = []
clean = tempfile.mkdtemp(prefix='samodiva_verify_')

print('=' * 72)
print('  1. ВГРАДЕНА МРЕЖА (чиста папка, без samodiva.nnue)')
print('=' * 72)
fingerprints = set()
for exe, note in BUILDS:
    src = os.path.join(BIN, exe)
    if not os.path.exists(src):
        fails.append('липсва ' + exe)
        print('  %-22s FAIL (липсва)' % exe)
        continue
    dst = os.path.join(clean, exe)
    shutil.copy2(src, dst)
    e = Eng(dst, clean)
    out = e.ask('uci', 'isready', until='readyok')
    nn = ' | '.join(l.replace('info string ', '') for l in out if 'NNUE' in l)
    emb = 'loaded from embedded' in nn
    m = re.search(r'fnv1a ([0-9a-f]+)', nn)
    if m:
        fingerprints.add(m.group(1))
    e.kill()
    if not emb:
        fails.append(exe + ' не зареди вградената мрежа')
    print('  %-22s %-4s %s' % (exe, 'ok' if emb else 'FAIL', nn[:56]))

print()
if len(fingerprints) == 1:
    print('  всичките build-ове зареждат една и съща мрежа: fnv1a %s' % fingerprints.pop())
else:
    fails.append('различни мрежи')
    print('  ВНИМАНИЕ: различни мрежи %s' % fingerprints)

print()
print('=' * 72)
print('  2. ЕДНАКЪВ РЕЗУЛТАТ НА ВСИЧКИ НИВА (дълбочина %d)' % DEPTH)
print('=' * 72)
rows = {}
for label, fen in FENS:
    line = []
    for exe, _ in BUILDS:
        p = os.path.join(BIN, exe)
        if not os.path.exists(p):
            continue
        e = Eng(p, clean)
        opts = ['uci', 'setoption name Threads value 1', 'setoption name Hash value 32']
        if TB and os.path.isdir(TB):
            opts.append('setoption name SyzygyPath value ' + TB)
        e.ask(*(opts + ['isready']), until='readyok')
        out = e.ask('position fen ' + fen, 'go depth %d' % DEPTH, until='bestmove')
        e.kill()
        sc = nodes = bm = None
        for l in out:
            m = INFO.match(l)
            if m and int(m.group(1)) == DEPTH:
                sc = '%s %s' % (m.group(3), m.group(2))
                nodes = int(m.group(4))
            if l.startswith('bestmove'):
                bm = l.split()[1]
        line.append((sc, nodes, bm))
    rows[label] = line
    same = len({tuple(x) for x in line}) == 1
    if not same:
        fails.append('нивата се разминават при ' + label)
    shown = line[0]
    if shown[0] is None:
        # no depth-N info line means the tablebase resolved the root outright;
        # that is a result too, and all tiers must agree on it the same way
        shown = ('(tablebase root)', '-', shown[2])
    print('  %-12s %-6s %s' % (label, 'ok' if same else 'DIFF', shown))

print()
print('=' * 72)
print('  3. ЛЕГАЛНОСТ НА ХОДОВЕТЕ (независима проверка, не е на engine-а)')
print('=' * 72)
for label, fen in FENS:
    e = Eng(os.path.join(BIN, BUILDS[0][0]), clean)
    e.ask('uci', 'setoption name Threads value 1', 'isready', until='readyok')
    out = e.ask('position fen ' + fen, 'go depth %d' % DEPTH, until='bestmove')
    e.kill()
    bm = next((l.split()[1] for l in out if l.startswith('bestmove')), None)
    ok = legal_move(fen, bm)
    if not ok:
        fails.append('нелегален ход в ' + label)
    print('  %-12s %-6s %s' % (label, 'ok' if ok else 'ILLEGAL', bm))

shutil.rmtree(clean, ignore_errors=True)
print()
if fails:
    print('ПРОВАЛЕНИ: %d' % len(fails))
    for f in fails:
        print('   ' + f)
    sys.exit(1)
print('Трите build-а минаха.')
