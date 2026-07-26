"""Journal capture and the Fold — the Experience Store's write path, per ADR-0002.

`add_entry`/`list_entries` are deterministic. `run_fold` is the journaling
agent's pipeline: it curates pending Journal Entries into schema-conforming
notes, then hands off the write-back to the deterministic journal-file I/O
in `capture.py`.
"""
