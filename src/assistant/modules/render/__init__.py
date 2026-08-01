"""The `render` module: the whole of what `pa` does (ADR-0005).

`pa render <dir>` turns a `resume.yaml` in that directory into a `resume.pdf`
beside it - or refuses, legibly, and writes nothing. See `cli.py` for the
command, `pipeline.py` for the two gates, and `pdf.py`/`resume.typ` for the
Typst compile.
"""
