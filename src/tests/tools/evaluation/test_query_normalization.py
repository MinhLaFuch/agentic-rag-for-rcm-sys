import pytest

from package.tools.evaluation.normalize_query_text import normalize_query_text
from package.tools.retrieval._helper import _tokenize


@pytest.mark.parametrize("raw,expected", [
    ("Pok\u00e9mon\u00ae \u2013 keyboard\u2122", "Pokemon - keyboard"),
    ("Fran\u00e7ais caf\u00e9", "Francais cafe"),
    ("10\u00d720 USB-C", "10 20 USB-C"),
    ("\u65e5\u672c\u8a9e", ""),
    (" \t ", ""),
    ("quiet usb-c keyboard", "quiet usb-c keyboard"),
])
def test_ascii_fold_and_raw_contract(raw, expected):
    assert normalize_query_text(raw, "raw") == raw
    folded = normalize_query_text(raw, "ascii_fold")
    assert folded == expected
    assert folded.isascii()
    if folded:
        _tokenize(folded)


def test_does_not_change_production_ascii_guard():
    with pytest.raises(ValueError):
        normalize_query_text("text", "unknown")
    with pytest.raises(Exception, match="ASCII"):
        _tokenize("Pok\u00e9mon")
