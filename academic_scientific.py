"""Load the editable academic/scientific transcription prompt."""

from pathlib import Path


ACADEMIC_SCIENTIFIC_PROMPT_PATH = Path(__file__).with_name(
    "academic_scientific_prompt.md"
)


def load_academic_scientific_prompt():
    """Read the prompt on demand so edits apply without restarting services."""
    return ACADEMIC_SCIENTIFIC_PROMPT_PATH.read_text(encoding="utf-8").strip()
