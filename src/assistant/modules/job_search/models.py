"""The shared `JobPosting` model, per the job-fit and resume-generation specs.

Produced once by the deterministic posting parser and consumed identically by
`pa jobs fit` and `pa jobs resume` - both features read the same parse.
"""

from typing import Literal

from pydantic import BaseModel

Market = Literal["sg", "remote"]


class JobPosting(BaseModel):
    """The deterministic parse of a pasted job posting."""

    title: str
    company: str
    market: Market
    requirements: list[str]
    keywords: list[str]
