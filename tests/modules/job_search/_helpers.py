def job_note_body(content: str) -> str:
    """The verbatim posting body of a rendered job note, stripped of its frontmatter."""
    _, _, body = content.partition("---\n")
    _, _, body = body.partition("---\n")
    return body
