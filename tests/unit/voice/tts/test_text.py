import pytest

from kosmos.voice.exceptions import InvalidSynthesisRequestError
from kosmos.voice.tts.text import prepare_text, segment_text


def test_preparation_removes_visual_markdown_and_preserves_meaning() -> None:
    text = "# Title\n- **Docker** uses `containers`. See [docs](https://example.com)."

    assert prepare_text(text) == "Title\nDocker uses containers. See docs."


def test_preparation_preserves_numbers_units_and_technical_terms() -> None:
    text = "A tensão é -12.5 V, o uso é 80%, com PostgreSQL e Kubernetes."

    assert prepare_text(text) == text


def test_preparation_retains_code_content_with_explicit_context() -> None:
    assert prepare_text("```bash\nrm --help\n```") == "Code block. rm --help"


def test_preparation_neutralizes_raw_phoneme_delimiters_and_controls() -> None:
    assert prepare_text("Olá\x00 [[ ba ]] 😊") == "Olá [ [ ba ] ] 😊"


def test_segmentation_prefers_sentence_boundaries_and_preserves_order() -> None:
    text = "Primeira frase curta. Segunda frase também curta. Terceira frase final."

    segments = segment_text(text, max_characters=32)

    assert segments == (
        "Primeira frase curta.",
        "Segunda frase também curta.",
        "Terceira frase final.",
    )
    assert " ".join(segments) == text


def test_segmentation_rejects_word_longer_than_limit() -> None:
    with pytest.raises(InvalidSynthesisRequestError, match="word exceeds"):
        segment_text("x" * 40, max_characters=32)
