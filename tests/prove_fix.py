"""Prove (or disprove) that the stalemate fix changes the search at all.

The fix only fires on a qsearch leaf that is a stalemate - 8 times in 446 239
qsearch nodes, always with <= 6 pieces.  So it can never show up in a root
score.  It CAN show up deeper in the tree, so: generate a lot of legal low-
material positions and search each one to a fixed depth with the build that has
the fix and the 1.5 build that does not.  Any position where the two disagree
is a direct demonstration that the fix changes what the engine computes.
"""
import os
import queue
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from minichess import Game

# Two builds to compare.  This script is the experiment behind docs/FINDINGS.md:
# pass any two executables and it reports where their searches disagree.
#   python prove_fix.py <exe-with-fix> <exe-without-fix>
A = sys.argv[1] if len(sys.argv) > 2 else os.path.join(ROOT, 'binaries', 'samodiva.exe')
B = sys.argv[2] if len(sys.argv) > 2 else A
DEPTH = 18
INFO = re.compile(r'^info depth \d+ multipv \d+ score (cp|mate) (-?\d+) nodes (\d+)')

SEEDS = [
    "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1",
    "8/8/8/8/8/1k6/2p5/K1R5 b - - 0 1",
    "8/8/8/3k4/8/8/3QK3/8 w - - 0 1",
    "8/8/8/4k3/8/8/4R3/4K3 w - - 0 1",
    "8/8/8/3k4/8/8/4P3/4K1R1 w - - 0 1",
    "7k/8/8/4k3/8/8/5P2/6R1 w - - 0 1",
    "8/8/8/3k4/8/8/3R4/3K4 w - - 0 1",
    "4k3/8/8/8/8/8/4P3/4K3 b - - 0 1",
    "8/8/8/8/1k6/1P6/1K6/8 w - - 0 1",
    "8/8/8/2k5/1P6/8/4K3/8 w - - 0 1",
    "8/5k2/8/2p5/2P5/8/5K2/8 w - - 0 1",
    "8/6k1/8/8/8/6P1/6K1/5PP1 w - - 0 1",
    "8/8/8/3k4/2B5/2P5/4K3/8 w - - 0 1",
    "8/8/8/3k4/3b4/3P4/3BK3/8 w - - 0 1",
    "8/8/8/3k4/2N5/3P4/4K3/8 w - - 0 1",
    "7k/8/8/4K3/8/8/6P1/7R w - - 0 1",
    "8/1k6/8/8/8/8/1K6/5R2 w - - 0 1",
    "8/8/8/4k3/8/2P5/2P1K3/6R1 w - - 0 1",
    "8/8/8/3k4/8/8/3NK3/7R w - - 0 1",
    "8/8/8/3k4/8/8/4K3/5QB1 w - - 0 1",
]

# shift every piece of a seed over a few squares -> many related endgames
def variants(fen, steps=(1, 2, 3, 4, 5, 6, 7)):
    b = fen.split()[0]
    rows = b.split('/')
    cells = []
    for i, row in enumerate(rows):
        r = 7 - i
        f = 0
        for ch in row:
            if ch.isdigit():
                f += int(ch)
            else:
                cells.append((ch, f, r))
                f += 1
    out = []
    for d in steps:
        nb = [['.'] * 8 for _ in range(8)]
        bad = False
        for ch, f, r in cells:
            nf, nr = f + d, r
            if nf > 7 or nr > 7 or (nb[nr][nf] != '.'):
                bad = True
                break
            nb[nr][nf] = ch
        if bad:
            continue
        rows2 = []
        for r in range(7, -1, -1):
            s, empty = '', 0
            for f in range(8):
                if nb[r][f] == '.':
                    empty += 1
                else:
                    if empty:
                        s += str(empty); empty = 0
                    s += nb[r][f]
            if empty:
                s += str(empty)
            rows2.append(s)
        out.append('/'.join(rows2) + ' w - - 0 1')
    return out


def illegal_reason(fen):
    """Why this FEN cannot start a real game, or None if it is fine.

    The earlier version only counted kings, so it let through positions like
    7k/8/8/4K3/8/8/6P1/7R w - where Rh1 already attacks Kh8 - black is in
    check with white to move, which is not a legal chess position at all.
    Those produce garbage from every engine and made the two builds look like
    they disagreed when they were both being fed nonsense.
    """
    try:
        g = Game(fen)
    except Exception as e:
        return 'unparseable (%s)' % e
    flat = [c for c in g.b if c != '.']
    if flat.count('K') != 1 or flat.count('k') != 1:
        return 'not exactly one king per side'
    if len(flat) < 4:
        return 'fewer than 4 pieces'
    if flat.count('P') > 8 or flat.count('p') > 8:
        return 'more than 8 pawns'
    for i, p in enumerate(g.b):
        if p in 'Pp' and (i // 8 in (0, 7)):
            return 'pawn on the first or eighth rank'
    turn = g.turn
    g.turn = 'b' if turn == 'w' else 'w'
    if g.in_check():
        g.turn = turn
        return 'the side NOT to move is in check'
    g.turn = turn
    if g.in_check():
        return None                    # legal: side to move may be in check
    return None


def legal(fen):
    return None if illegal_reason(fen) else Game(fen)


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

    def score(self, fen, depth):
        self.w('ucinewgame'); self.w('isready'); self.rt('readyok')
        self.w('position fen ' + fen)
        self.w('go depth %d' % depth)
        s = None
        while True:
            l = self.q.get()
            if l is None:
                break
            m = INFO.match(l)
            if m:
                s = (m.group(1), int(m.group(2)))
            if l.startswith('bestmove'):
                break
        return s

    def close(self):
        try:
            self.w('quit'); self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


import queue  # noqa: E402

fens = []
for s in SEEDS:
    fens.append(s)
    fens.extend(variants(s))
dropped = []
keep = []
for f in fens:
    why = illegal_reason(f)
    if why:
        dropped.append((f, why))
    else:
        keep.append(f)
fens = keep
seen = set()
uniq = []
dropped = [(f, w) for f, w in dropped if not (f in seen or seen.add(f))]
print('generated %d positions, %d rejected as illegal/unusable, %d kept'
      % (len(fens) + len(dropped), len(dropped), len(fens)))
for f, why in dropped[:12]:
    print('   dropped %-42s %s' % (f, why))
if len(dropped) > 12:
    print('   ... and %d more' % (len(dropped) - 12))
fens = [f for f in fens if legal(f)]
# dedupe
seen, uniq = set(), []
for f in fens:
    if f not in seen:
        seen.add(f); uniq.append(f)
print('generated %d legal low-material positions, searching each at depth %d' % (len(uniq), DEPTH))

ea, eb = Eng(A), Eng(B)
diffs, same = [], 0
t0 = time.time()
for i, f in enumerate(uniq):
    sa = ea.score(f, DEPTH)
    sb = eb.score(f, DEPTH)
    if sa is None or sb is None:
        continue
    if sa == sb:
        same += 1
    else:
        diffs.append((f, sa, sb))
    if (i + 1) % 40 == 0:
        print('  %3d/%d  identical so far: %d, differing: %d  (%.0f s)'
              % (i + 1, len(uniq), same, len(diffs), time.time() - t0))
ea.close(); eb.close()

print()
print('=' * 72)
print('positions where the two builds DISAGREE: %d of %d' % (len(diffs), same + len(diffs)))
print('=' * 72)
for f, sa, sb in diffs[:40]:
    print('  %-42s  1.5=%-10s patfix=%-10s' % (f, '%s %s' % (sa[1], sa[0][:2]), '%s %s' % (sb[1], sb[0][:2])))
