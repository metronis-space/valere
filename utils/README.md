# Shared utilities

`utils` contains dependency-neutral infrastructure used by more than one
phase. Domain engines do not live here.

- `artifacts.py` owns canonical JSON, SHA-256 fingerprints, integrity checks,
  document loading, and atomic JSON/YAML writes.
- `errors.py` owns the common error base and validation-report primitives.
- `values.py` owns unresolved-value, date/time, lookup, and unique-index helpers.
- `catalogs.py` owns closed cross-phase workflow and M&A catalogs.
- `pov.py` is the single source of truth for the bounded Harvey LAB POV IDs.
- `cli.py` owns shared JSON console rendering.

`scope` and `truth` may expose compatibility imports, but neither phase should
import infrastructure from the other.
