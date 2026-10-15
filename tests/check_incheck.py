"""Cross-check minichess.in_check() against a hand-rolled, independent one."""
import sys

sys.path.insert(0, r'D:\Downloads\samodiva_1.5_test')
from minichess import Game, sq   # noqa: E402


def independent_attacked(b, f, r, by_white):
    """Deliberately naive: walk every ray / jump from every enemy piece."""
    want = 'w' if by_white else 'b'
    for i, p in enumerate(b):
        if p == '.' or p.isupper() != by_white:
            continue
        ef, er = i % 8, i // 8
        kind = p.upper()
        df, dr = ef - f, er - r
        if kind == 'P':
            # a pawn on (ef,er) attacks (f,r) iff |df| == 1 and the target is one
            # rank "in front of" it in the direction the pawn moves
            step = -1 if by_white else 1
            if abs(df) == 1 and dr == step:
                return True
            continue
        if kind == 'N':
            if (abs(df), abs(dr)) in ((1, 2), (2, 1)):
                return True
            continue
        if kind == 'K':
            if max(abs(df), abs(dr)) == 1:
                return True
            continue
        diag = abs(df) == abs(dr) and df != 0
        line = (df == 0) != (dr == 0)
        if kind in ('B', 'R', 'Q'):
            if (kind == 'B' and diag) or (kind == 'R' and line) or (kind == 'Q' and (diag or line)):
                # walk from the enemy piece to the target: nothing may be between
                sf = (ef > f) - (ef < f)
                sr = (er > r) - (er < r)
                cf, cr = ef + sf, er + sr
                while (cf, cr) != (f, r):
                    if b[sq(cf, cr)] != '.':
                        break
                    cf += sf; cr += sr
                else:
                    return True
    return False


def indep_in_check(g):
    kc = 'K' if g.turn == 'w' else 'k'
    for i, p in enumerate(g.b):
        if p == kc:
            return independent_attacked(g.b, i % 8, i // 8, g.turn == 'b')
    return False


TESTS = [
    '8/8/8/6k1/5B2/5P2/7K/8 w - - 0 1',
    '8/8/8/5k2/4B3/4P3/6K1/8 w - - 0 1',
    '8/8/8/4k3/3B4/3P4/5K2/8 w - - 0 1',
    '8/8/8/3k4/2B5/2P5/4K3/8 w - - 0 1',
    '7k/8/8/4K3/8/8/6P1/7R w - - 0 1',
    '8/8/8/3k4/2N5/3P4/4K3/8 w - - 0 1',
    '8/8/8/4k3/8/8/4P3/4K1R1 w - - 0 1',
]

bad = 0
for fen in TESTS:
    g = Game(fen)
    mine = g.in_check()
    theirs = indep_in_check(g)
    mark = 'ok' if mine == theirs else 'DISAGREE'
    if mine != theirs:
        bad += 1
    print('%-44s minichess=%-5s independent=%-5s %s' % (fen, mine, theirs, mark))
print('\ndisagreements: %d of %d' % (bad, len(TESTS)))
