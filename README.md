# Samodiva 1.5 — embedded network build

A build of **Samodiva 1.5** whose neural network lives *inside* the executable.

No `samodiva.nnue` next to it. Nothing to install, nothing to copy, and no way
to end up silently playing 250 Elo weaker because one file is missing.

> **The engine source is proprietary and is not in this repository.** What is
> here are the binaries, the network, the measurements behind them and the
> scripts that verify all of it. See [LICENSE](#license).

---

## Download

From the Releases page, or from `binaries/` in this repository.

| File | Compiled for | Use it on |
|---|---|---|
| `samodiva.exe` | `-march=native` (Zen 1 / AVX2) | this build machine, fastest |
| **`samodiva_v2.exe`** | `-march=x86-64-v2` (SSE4.2) | **any CPU from 2008 on — share this one** |
| `samodiva_legacy.exe` | `-march=x86-64` (SSE2) | any x86-64 CPU, 2003 and older |

All three return **identical scores, node counts and moves**. Only speed
differs. Measured on a Ryzen 5 2600 at fixed depth, single thread:

| Position | native | v2 | legacy |
|---|---|---|---|
| startpos d14 | 81 ms | 82 ms (+1%) | 92 ms (+14%) |
| kiwipete d14 | 318 ms | 326 ms (+3%) | 378 ms (+19%) |
| endgame d17 | 195 ms | 197 ms (+1%) | 287 ms (+47%) |

`v2` costs 1–6%. That is the price of not dying with an illegal instruction on
a machine that has no AVX2, and it is worth paying when you do not know what
hardware is on the other end.

---

## What changed against the 1.5 release

The engine in the [Samodiva repository](https://github.com/nkralev76-hue/Samodiva)
reads `samodiva.nnue` from disk and falls back to the classical evaluation when
the file is absent — about 250 Elo weaker, with only an `info string` to say so.

This build has the same network compiled in:

```
NNUE: file 'samodiva.nnue' cannot be opened - using the network embedded in this
executable (fnv1a 8632e28a)
NNUE loaded from embedded in executable (fnv1a 8632e28a, 394760 bytes)
```

A file next to the executable still wins if one is present, so dropping in a
different network for an experiment works exactly as before.

Also fixed: a bare `go` with no argument used to leave the engine waiting for a
`stop` that a GUI may never send. It now reports what it is doing and behaves
the way UCI callers expect. `go depth N` and the other forms are unaffected.

---

## Tablebases

Syzygy support is compiled in. Point it at a tablebase directory:

```
setoption name SyzygyPath value E:\path\to\syzygy
```

| Option | Default | Meaning |
|---|---|---|
| `SyzygyPath` | empty | tablebase directory |
| `SyzygyProbeDepth` | 1 | depth from which to probe |
| `SyzygyProbeLimit` | 7 | maximum pieces to probe |
| `Syzygy50MoveRule` | true | honour the fifty-move rule |

A 5-piece set is 293 files and makes the engine resolve KQ / KR / KB / KN / KP
endgames outright, from the root, with no search at all. Six- and seven-piece
positions still depend on the search.

---

## Verify it yourself

Everything quoted above is reproducible from this repository.

```bat
python tests\verify_binaries.py     :: embedded net, tier agreement, legal moves
python tests\tb_check.py             :: tablebase detection, probing, agreement
python tests\bench_tiers.py          :: the timing table above
python tests\test_go_modes.py        :: the `go` regression
python tests\check_incheck.py        :: the position validator
```

`verify_binaries.py` copies each executable into an empty folder and reads the
engine's own output, so it tests what actually ships rather than what the build
claims. Set `SYZYGY_PATH` to include tablebase probing.

To reproduce the measurements in `docs/FINDINGS.md` you need two builds to
compare:

```bat
python tests\prove_fix.py       <exe-with-fix> <exe-without-fix>
python tests\bestmove_check.py  <exe-with-fix> <exe-without-fix>
```

---

## What the measurements said

`docs/FINDINGS.md` is the full report. The short version:

A stalemate check was added to the qsearch and the killer-reset line removed,
then six builds were compared. The result was worth the trouble:

- The stalemate fix **changes the search** in 8 of 24 legal endgames, by up to
  470 centipawns, and uses 1.5% fewer nodes.
- It is **not measurably stronger in games**: in 23 of those 24 positions it
  chooses the exact same move.
- 690 endgame games produced a dead heat, and the reason is not that the
  engines are equal. The side to move won 87% of the decisive games, which
  swamps any difference between builds.

That last point is the useful one. Real stalemates appear in 8 leaves out of
446 239 qsearch nodes, always with six pieces or fewer. Diluted across a
32-piece, 80-move game, that signal is nothing. **The time control was never
the right instrument** — the position set was.

Full details, including the confidence intervals and the traps in the test
harness itself, are in [`docs/FINDINGS.md`](docs/FINDINGS.md).

---

## License

Three separate things, with separate terms.

| What | Terms |
|---|---|
| The binaries in `binaries/`, the docs, the test scripts | MIT — see [LICENSE](LICENSE) |
| `samodiva.nnue`, the network | MIT — see [LICENSE](LICENSE) |
| The engine **source code** | **Proprietary. Not distributed here, not in this repository.** |

The binaries link against the Syzygy tablebase probing code by basil00 and
Jon Dart, which is MIT licensed. Their notices are intact and must stay —
see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

The name "Samodiva" is not covered by the licence.

Consistent with the [Samodiva repository](https://github.com/nkralev76-hue/Samodiva),
this build is MIT for binaries and networks. The source is not published.
