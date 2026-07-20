# FileProvider test datasets

Deterministic fixtures for M1.2. Never edited in place — replace wholesale via
a reviewed commit (same discipline as the golden dataset).

- `fileprovider/` — small synthetic dataset (arithmetic prices, fictional IDs
  `SYN-AAA`/`SYN-BBB`). Daily Feb 2026, one 5m intraday file, quotes, snapshot.
- `fileprovider_sample/` — sanitized, minimal, real-world-*shaped* dataset
  (real symbols RELIANCE/TCS with real ISINs, but **fictional prices**). Proves
  the provider handles realistic identifiers and multi-index snapshots.

Both are used by `tests/data_layer/test_file_provider.py` and the contract suite.
