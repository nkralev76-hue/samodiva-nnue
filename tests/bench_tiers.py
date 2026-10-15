"""Speed of the three production tiers on this machine.

Same source, same depth, one thread, fixed hash, NNUE on - so the only variable
is which instruction sets the compiler was allowed to use.
"""
import os
import queue
import re
import subprocess
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, 'binaries')
TB = os.environ.get('SYZYGY_PATH', r'E:\OLDPC\Chess\syzygy')
INFO = re.compile(r'^info depth (\d+) multipv \d+ score (cp|mate) (-?\d+) nodes (\d+) '
                  r'nps (\d+) .* time (\d+) pv(.*)$')

TIERS = [('samodiva.exe        native (znver1, AVX2)', os.path.join(BIN, 'samodiva.exe')),
         ('samodiva_v2.exe     x86-64-v2 (SSE4.2)',    os.path.join(BIN, 'samodiva_v2.exe')),
         ('samodiva_legacy.exe x86-64 (SSE2)',         os.path.join(BIN, 'samodiva_legacy.exe'))]

POSITIONS = [
    ('startpos',  'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', 14),
    ('kiwipete',  'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1', 14),
    ('position 3', 'r2q1rk1/pP1p2pp/Q4n2/bbp1p3/Np6/1B3NBn/pPPP1PPP/R3K2R b KQ - 0 1', 14),
    ('endgame',  '8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1', 17),
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
            self.p.stdin.write(c + '\n')
        self.p.stdin.flush()
        out = []
        while True:
            l = self.q.get()
            if l is None:
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


clean = tempfile.mkdtemp(prefix='samodiva_bench_')
TB_HERE = TB if os.path.isdir(TB) else ''
engines = {}
for label, path in TIERS:
    e = Eng(path, clean)
    opts = ['uci', 'setoption name Threads value 1', 'setoption name Hash value 32',
            'setoption name Use NNUE value true']
    if TB_HERE:
        opts.append('setoption name SyzygyPath value ' + TB_HERE)
    e.ask(*(opts + ['isready']), until='readyok')
    engines[label] = e

if not TB_HERE:
    print('няма SyzygyPath (%s) - измервам без таблица' % TB)
    print()

print('AMD Ryzen 5 2600 (Zen 1), 1 нишка, hash 32 MB, NNUE вкл., Syzygy вкл.')print()
print('%-46s %10s %10s %10s' % ('build', 'native', 'v2', 'legacy'))
print('-' * 80)

for name, fen, depth in POSITIONS:
    row = []
    ref = None
    for label, _ in TIERS:
        best = None
        for _rep in range(3):                      # 3 repeats, keep the fastest
            e = engines[label]
            e.ask('ucinewgame', 'isready', until='readyok')
            out = e.ask('position fen ' + fen, 'go depth %d' % depth, until='bestmove')
            for l in out:
                m = INFO.match(l)
                if m and int(m.group(1)) == depth:
                    best = (int(m.group(4)), int(m.group(6)), m.group(7).split()[0])
        row.append(best)
    ref = row[0]
    same = all(r and ref and r[0] == ref[0] and r[2] == ref[2] for r in row)
    cells = []
    for r in row:
        if not r:
            cells.append('?')
            continue
        d = 100.0 * (r[1] - ref[1]) / ref[1] if ref else 0
        cells.append('%5d ms%s' % (r[1], '' if abs(d) < 0.5 else ' %+4.0f%%' % d))
    print('%-14s d%-3d nodes=%-8d move=%-7s  %s' %
          (name, depth, ref[0], ref[2], '  '.join('%-16s' % c for c in cells)))
    if not same:
        print('   ВНИМАНИЕ: build-овете не са съгласни за тази позиция')

print()
print('%-14s %s' % ('', 'еднакви възли и ход навсякъде: проверено по-горе'))
for label, _ in TIERS:
    engines[label].kill()
