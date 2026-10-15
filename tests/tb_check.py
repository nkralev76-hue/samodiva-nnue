"""How well does Syzygy work on each build?

All six variants share the same tablebase code, but the stalemate fix does touch
qsearch, and TB wins short-circuit before qsearch ever runs - so the two
interact.  This measures, per build:

  * how many pieces the tablebase set on this machine actually covers
  * whether tbhits is non-zero on positions inside that coverage
  * whether all builds agree on the move (they must - TB is deterministic)
  * whether anything crashes on an odd position

Tested in a clean folder, with the tablebase pointed at E:\\OLDPC\\Chess\\syzygy.
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
sys.path.insert(0, HERE)
from minichess import Game   # noqa: E402

TB = os.environ.get('SYZYGY_PATH', r'E:\OLDPC\Chess\syzygy')
DEPTH = 12

BUILDS = [
    ('samodiva.exe  native',  os.path.join(ROOT, 'binaries', 'samodiva.exe')),
    ('samodiva_v2.exe',       os.path.join(ROOT, 'binaries', 'samodiva_v2.exe')),
    ('samodiva_legacy.exe',   os.path.join(ROOT, 'binaries', 'samodiva_legacy.exe')),
]

# (label, fen) - deliberately a mix: inside 5-man coverage and outside it
POSITIONS = [
    ('KQ vs K   (4)',  '8/8/8/3k4/8/8/3QK3/8 w - - 0 1'),
    ('KR vs K   (4)',  '8/8/8/4k3/8/8/4R3/4K3 w - - 0 1'),
    ('KQP vs K  (5)',  '8/8/8/4k3/8/8/3PK3/6Q1 w - - 0 1'),
    ('KBP vs K  (5)',  '8/8/8/4k3/3B4/4P3/5K2/8 w - - 0 1'),
    ('KNP vs K  (5)',  '8/8/8/4k3/3N4/4P3/5K2/8 w - - 0 1'),
    ('KBB vs K  (5)',  '8/8/8/4k3/2B1B3/8/5K2/8 w - - 0 1'),
    ('KBN vs K  (5)',  '8/8/8/4k3/2B1N3/8/5K2/8 w - - 0 1'),
    ('KPP vs K  (5)',  '8/8/8/4k3/8/2P5/2P1K3/8 w - - 0 1'),
    ('KRP vs K  (5)',  '8/8/8/4k3/8/8/4P3/4K1R1 w - - 0 1'),
    ('KRPP vs K (6)',  '8/8/8/4k3/8/2P5/2P1K3/6R1 w - - 0 1'),
    ('KRBNPvsK (6)',  '8/8/8/4k3/2B1N3/8/3PK3/6R1 w - - 0 1'),
]


class Eng:
    def __init__(self, path, cwd):
        self.q = queue.Queue()
        self.p = subprocess.Popen([path], cwd=cwd, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, bufsize=1)
        threading.Thread(target=self._r, daemon=True).start()
        self.alive = True

    def _r(self):
        for line in self.p.stdout:
            self.q.put(line.strip())
        self.q.put(None)
        self.alive = False

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


clean = tempfile.mkdtemp(prefix='samodiva_tb_')
print('таблицата: %s  ->  %d файла' % (TB, len(os.listdir(TB)) if os.path.isdir(TB) else 0))
print()

# reject anything that is not a legal position before feeding it to an engine
good = []
for label, fen in POSITIONS:
    g = Game(fen)
    turn = g.turn
    g.turn = 'b' if turn == 'w' else 'w'
    if g.in_check():
        print('  ПУСНАТ (нелегална): %s' % label)
        continue
    g.turn = turn
    good.append((label, fen))
print('проверени позиции: %d от %d\n' % (len(good), len(POSITIONS)))

print('=' * 96)
print('  1. ОТКРИВАНЕ НА ТАБЛИЦАТА (всички build-ове трябва да кажат едно и също)')
print('=' * 96)
detect = {}
for name, path in BUILDS:
    e = Eng(path, clean)
    out = e.ask('uci', 'setoption name SyzygyPath value ' + TB, 'isready', until='readyok')
    e.kill()
    msg = next((l.replace('info string ', '') for l in out
                if l.startswith('info string') and 'Syzygy:' in l), '(няма ред)')
    detect[name] = msg
    print('  %-22s %s' % (name, msg))
vals = set(detect.values())
print()
print('  всички build-ове откриват едно и също: %s' % ('ДА' if len(vals) == 1 else 'НЕ -> ' + str(vals)))

print()
print('=' * 96)
print('  2. ТЬРСЕНЕ С ТАБЛИЦА - tbhits и избраният ход')
print('=' * 96)
results = {}
for name, path in BUILDS:
    e = Eng(path, clean)
    e.ask('uci', 'setoption name Threads value 1', 'setoption name Hash value 32',
          'setoption name SyzygyPath value ' + TB, 'isready', until='readyok')
    row = []
    for label, fen in good:
        out = e.ask('position fen ' + fen, 'go depth %d' % DEPTH, until='bestmove')
        hits = 0
        bm = None
        tbroot = False
        for l in out:
            # tbhits is a field INSIDE the info line, not a line of its own
            m = re.search(r'tbhits (\d+)', l)
            if m:
                hits = int(m.group(1))
            if 'tablebase root move' in l:
                tbroot = True
            if l.startswith('bestmove'):
                bm = l.split()[1]
        row.append((label, hits, bm, tbroot))
    e.kill()
    results[name] = row
    tot = sum(h for _, h, _, _ in row)
    nz = sum(1 for _, h, _, _ in row if h > 0)
    root = sum(1 for _, _, _, t in row if t)
    print('  %-22s tbhits>0: %2d/%2d   общо: %6d   root-проба: %2d'
          % (name, nz, len(row), tot, root))

print()
print('=' * 96)
print('  3. СЪГЛАСУВАНОСТ - всички build-ове трябва да изберат ЕДИН И СЪЩИ ход')
print('=' * 96)
disagree = 0
for i, (label, _) in enumerate(good):
    moves = {n: results[n][i][2] for n, _ in BUILDS}
    hits = {n: results[n][i][1] for n, _ in BUILDS}
    root = {n: results[n][i][3] for n, _ in BUILDS}
    same = len(set(moves.values())) == 1
    sameh = len(set(hits.values())) == 1
    if not same:
        disagree += 1
    print('  %-16s %-6s move=%-7s hits=%-5s root=%-5s %s%s'
          % (label, 'ok' if same else 'DIFF', list(moves.values())[0],
             list(hits.values())[0], list(root.values())[0], '' if same else '-> ' + str(moves),
             '' if sameh else '  (hits: %s)' % hits))
print()
print('  позиции, в които build-овете не са съгласни: %d от %d' % (disagree, len(good)))

print()
print('=' * 96)
print('  4. СТАБИЛНОСТ - нелегална позиция (черният в шах при бял на ход)')
print('=' * 96)
odd = '7k/8/8/4K3/8/8/6P1/7R w - - 0 1'   # Rh1 вече атакува Kh8 -> нелегална
for name, path in BUILDS[:4]:
    e = Eng(path, clean)
    out = e.ask('uci', 'setoption name SyzygyPath value ' + TB, 'isready', until='readyok')
    out += e.ask('position fen ' + odd, 'go depth ' + str(DEPTH), until='bestmove')
    e.kill()
    dead = any('умрял' in l for l in out)
    bm = next((l.split()[1] for l in out if l.startswith('bestmove')), '-')
    print('  %-16s %-6s bestmove=%s' % (name, 'CRASH' if dead else 'ok', bm))

shutil.rmtree(clean, ignore_errors=True)
