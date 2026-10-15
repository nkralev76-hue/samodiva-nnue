"""
Mini chess board used only for adjudication:
replays the game so that threefold repetition and the 50-move rule are detected
properly, and so a 'bestmove 0000' can be told apart (checkmate) from
'bestmove 0000' (stalemate).

No legality checking - the engine only ever sends legal moves.
"""

FILES = 'abcdefgh'
KNIGHT_D = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
KING_D = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
BISHOP_D = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
ROOK_D = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def sq(f, r):
    return r * 8 + f


def piece_color(p):
    return 'w' if p.isupper() else 'b'


def is_piece(p, color=None, types=None):
    if p == '.':
        return False
    if color and piece_color(p) != color:
        return False
    if types and p.lower() not in types:
        return False
    return True


class Game:
    def __init__(self, fen):
        parts = fen.split()
        self.b = ['.'] * 64
        rows = parts[0].split('/')
        for i, row in enumerate(rows):
            r = 7 - i
            f = 0
            for ch in row:
                if ch.isdigit():
                    f += int(ch)
                else:
                    self.b[sq(f, r)] = ch
                    f += 1
        self.turn = parts[1]
        self.cast = '' if len(parts) < 2 or parts[2] == '-' else parts[2]
        self.ep = None
        if len(parts) > 3 and parts[3] != '-':
            self.ep = sq(FILES.index(parts[3][0]), int(parts[3][1]) - 1)
        self.half = int(parts[4]) if len(parts) > 4 else 0
        self.full = int(parts[5]) if len(parts) > 5 else 1
        self.hm_rep = {self.key(): 1}
        self.reps = 1
        self.fifty = self.half >= 100
        self.move_no = 0

    def to_fen(self):
        rows = []
        for r in range(7, -1, -1):
            s, empty = '', 0
            for f in range(8):
                p = self.b[sq(f, r)]
                if p == '.':
                    empty += 1
                else:
                    if empty:
                        s += str(empty); empty = 0
                    s += p
            if empty:
                s += str(empty)
            rows.append(s)
        ep = '-' if self.ep is None else FILES[self.ep % 8] + str(self.ep // 8 + 1)
        return '/'.join(rows) + ' ' + self.turn + ' ' + (self.cast or '-') + ' ' + ep + ' %d %d' % (self.half, self.full)

    # ---------- position key (piece placement + side + castling + ep) ----------
    def key(self):
        rows = []
        for r in range(7, -1, -1):
            s, empty = '', 0
            for f in range(8):
                p = self.b[sq(f, r)]
                if p == '.':
                    empty += 1
                else:
                    if empty:
                        s += str(empty); empty = 0
                    s += p
            if empty:
                s += str(empty)
            rows.append(s)
        ep = '-' if self.ep is None else FILES[self.ep % 8] + str(self.ep // 8 + 1)
        return '/'.join(rows) + ' ' + self.turn + ' ' + (self.cast or '-') + ' ' + ep

    # ---------- attacks ----------
    def _attacked(self, f, r, by_white):
        b = self.b
        # pawns
        pr = r - 1 if by_white else r + 1
        if 0 <= pr <= 7:
            for df in (-1, 1):
                ff = f + df
                if 0 <= ff <= 7 and b[sq(ff, pr)] == ('P' if by_white else 'p'):
                    return True
        # knights
        for df, dr in KNIGHT_D:
            ff, rr = f + df, r + dr
            if 0 <= ff <= 7 and 0 <= rr <= 7 and b[sq(ff, rr)] == ('N' if by_white else 'n'):
                return True
        # king
        for df, dr in KING_D:
            ff, rr = f + df, r + dr
            if 0 <= ff <= 7 and 0 <= rr <= 7 and b[sq(ff, rr)] == ('K' if by_white else 'k'):
                return True
        # sliders
        for dirs, pieces in ((ROOK_D, 'RQ'), (BISHOP_D, 'BQ')):
            for df, dr in dirs:
                ff, rr = f + df, r + dr
                while 0 <= ff <= 7 and 0 <= rr <= 7:
                    p = b[sq(ff, rr)]
                    if p != '.':
                        if piece_color(p) == ('w' if by_white else 'b') and p.upper() in pieces:
                            return True
                        break
                    ff += df; rr += dr
        return False

    def in_check(self):
        kc = 'K' if self.turn == 'w' else 'k'
        for i, p in enumerate(self.b):
            if p == kc:
                return self._attacked(i % 8, i // 8, self.turn == 'b')
        return False

    # ---------- move application ----------
    def apply(self, mv):
        f0, r0 = FILES.index(mv[0]), int(mv[1]) - 1
        f1, r1 = FILES.index(mv[2]), int(mv[3]) - 1
        promo = mv[4] if len(mv) > 4 else ''
        b = self.b
        p = b[sq(f0, r0)]
        pl = p.lower()
        if p == '.':
            raise ValueError('move %s starts on an empty square' % mv)

        if pl == 'k' and abs(f1 - f0) == 2:             # castling
            if f1 == 6:
                b[sq(5, r0)] = b[sq(7, r0)]; b[sq(7, r0)] = '.'
            else:
                b[sq(3, r0)] = b[sq(0, r0)]; b[sq(0, r0)] = '.'
            b[sq(f0, r0)] = '.'
            b[sq(f1, r1)] = p
            self.half += 1
        else:
            captured = b[sq(f1, r1)] != '.'
            if pl == 'p' and f1 != f0 and not captured:   # en passant
                b[sq(f1, r0)] = '.'
                captured = True
            if pl == 'p' or captured:
                self.half = 0
            else:
                self.half += 1
            b[sq(f0, r0)] = '.'
            b[sq(f1, r1)] = (promo.upper() if self.turn == 'w' else promo) if promo else p

        # castling rights
        lost = set()
        for (ff, rr) in ((f0, r0), (f1, r1)):
            if (ff, rr) == (4, 0):
                lost |= {'K', 'Q'}
            elif (ff, rr) == (4, 7):
                lost |= {'k', 'q'}
            elif (ff, rr) == (0, 0):
                lost.add('Q')
            elif (ff, rr) == (7, 0):
                lost.add('K')
            elif (ff, rr) == (0, 7):
                lost.add('q')
            elif (ff, rr) == (7, 7):
                lost.add('k')
        self.cast = ''.join(c for c in self.cast if c not in lost)

        # en passant square
        self.ep = sq((f0 + f1) // 2, r0) if (pl == 'p' and abs(r1 - r0) == 2) else None

        if self.turn == 'b':
            self.full += 1
        self.turn = 'b' if self.turn == 'w' else 'w'
        self.move_no += 1

        k = self.key()
        self.hm_rep[k] = self.hm_rep.get(k, 0) + 1
        self.reps = self.hm_rep[k]
        if self.half >= 100:
            self.fifty = True
        return self
