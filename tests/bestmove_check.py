"""Do the two builds actually play differently, or is the eval gap cosmetic?

The score differs on 8 of 24 legal endgames, but what decides games is the move.
For every legal position: both builds search to depth 18, and we compare score,
bestmove and node count.  A differing score with the same bestmove explains why
690 endgame games produced a dead heat.
"""
import os
import queue
import re
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import prove_fix as pf   # noqa: E402

# Two builds to compare:
#   python bestmove_check.py <exe-with-fix> <exe-without-fix>
A = sys.argv[1] if len(sys.argv) > 2 else os.path.join(ROOT, 'binaries', 'samodiva.exe')
B = sys.argv[2] if len(sys.argv) > 2 else A
DEPTH = 18
INFO = re.compile(r'^info depth (\d+) multipv \d+ score (cp|mate) (-?\d+) nodes (\d+)')


class Eng:
    def __init__(self, exe):
        self.q = queue.Queue()
        self.p = subprocess.Popen([exe], cwd=os.path.dirname(exe) or '.', stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        threading.Thread(target=self._r, daemon=True).start()
        self.w('uci'); self.rt('uciok')
        self.w('setoption name Threads value 1'); self.w('setoption name Hash value 32')
        self.w('isready'); self.rt('readyok')

    def _r(self):
        for line in self.p.stdout:
            self.q.put(line.strip())
        self.q.put(None)

    def w(self, s):
        self.p.stdin.write(s + '\n'); self.p.stdin.flush()

    def rt(self, tok):
        while True:
            l = self.q.get()
            if l is None or l.startswith(tok):
                return

    def run(self, fen, depth):
        self.w('ucinewgame'); self.w('isready'); self.rt('readyok')
        self.w('position fen ' + fen)
        self.w('go depth %d' % depth)
        sc, nodes, bm = None, None, None
        while True:
            l = self.q.get()
            if l is None:
                break
            m = INFO.match(l)
            if m:
                sc = (m.group(2), int(m.group(3)))
                nodes = int(m.group(4))
            if l.startswith('bestmove'):
                bm = l.split()[1]
                break
        return sc, nodes, bm

    def close(self):
        try:
            self.w('quit'); self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


fens = []
for s in pf.SEEDS:
    fens.append(s)
    fens.extend(pf.variants(s))
seen, legal = set(), []
for f in fens:
    if f not in seen and not pf.illegal_reason(f):
        seen.add(f)
        legal.append(f)

ea, eb = Eng(A), Eng(B)
print('%d legal positions, depth %d\n' % (len(legal), DEPTH))
print('%-42s %-16s %-16s %-6s %-6s' % ('position', '1.5 score/move', 'fix score/move', 'same', 'nodes'))
print('-' * 100)
diff_score = same_move = 0
node_a = node_b = 0
for f in legal:
    sa, na, ba = ea.run(f, DEPTH)
    sb, nb, bb = eb.run(f, DEPTH)
    node_a += na
    node_b += nb
    same = 'yes' if ba == bb else 'NO'
    if sa != sb:
        diff_score += 1
    if ba == bb:
        same_move += 1
    print('%-42s %6s %-9s %6s %-9s %-6s %7d %7d'
          % (f, sa[1], sa[0][:2], sb[1], sb[0][:2], same, na, nb))
ea.close(); eb.close()

print()
print('scores differ            : %d of %d' % (diff_score, len(legal)))
print('bestmove identical      : %d of %d' % (same_move, len(legal)))
print('total nodes 1.5 / fix   : %d / %d  (fix uses %+.1f%%)'
      % (node_a, node_b, 100.0 * (node_b - node_a) / node_a))
