# Golden Dataset (skeleton — populated in Phase 1)

Frozen reference data + expected outputs. Any diff in expected outputs must be
an intentional, reviewed change (ATHENA-002 §12).

## Planned composition (T-3)

- ~50 NSE instruments × 2 years daily candles + 30 sessions of 5-minute candles
- Must include: a stock split, a bonus issue, a symbol rename, a circuit-locked
  session, an F&O-ban entry, an exchange holiday, a Muhurat session, a gap-open day

## Layout

```
tests/golden/
├── data/        # frozen input candles, corporate actions, calendar (Phase 1)
└── expected/    # expected evidence/scores/decisions per golden run (Phase 3)
```

Populated from FileProvider ingestions once Phase 1 lands. Nothing in `data/`
may ever be edited in place — replace wholesale with a reviewed commit.
