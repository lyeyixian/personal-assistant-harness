"""Layout: the fixed Typst template and the compile step that drives it.

The rest of the module renders through `render_resume_pdf`; the payload shape
the template consumes is private to this package. `TEMPLATE_PATH` is exported
so tests can guard the template's extraction-safety settings.
"""

from assistant.modules.job_search.render.pdf import (
    TEMPLATE_PATH,
    ResumeOverflowError,
    render_resume_pdf,
)

__all__ = ["TEMPLATE_PATH", "ResumeOverflowError", "render_resume_pdf"]
