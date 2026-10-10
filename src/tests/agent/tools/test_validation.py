"""Tests for validation helpers in tools/base."""

import pytest

from package.tools.base import (
    ToolInputError,
    candidate_ids,
    check_top_k,
    validate_dict,
    validate_float,
    validate_int,
    validate_list_like,
)


class TestValidateListLike:
    def test_accepts_list(self):
        assert validate_list_like([1, 2, 3], "test") == [1, 2, 3]

    def test_accepts_tuple(self):
        assert validate_list_like((1, 2, 3), "test") == [1, 2, 3]

    def test_rejects_string(self):
        with pytest.raises(ToolInputError, match="must be a list or tuple"):
            validate_list_like("abc", "test")

    def test_rejects_int(self):
        with pytest.raises(ToolInputError, match="must be a list or tuple"):
            validate_list_like(123, "test")

    def test_rejects_dict(self):
        with pytest.raises(ToolInputError, match="must be a list or tuple"):
            validate_list_like({"a": 1}, "test")


class TestValidateInt:
    def test_accepts_int(self):
        assert validate_int(5, "test") == 5

    def test_rejects_bool(self):
        with pytest.raises(ToolInputError, match="must be an integer, not a boolean"):
            validate_int(True, "test")
        with pytest.raises(ToolInputError, match="must be an integer, not a boolean"):
            validate_int(False, "test")

    def test_rejects_float_with_fraction(self):
        with pytest.raises(ToolInputError, match="must be an integer, got float"):
            validate_int(5.7, "test")

    def test_rejects_float_whole_but_explicitly_requires_int(self):
        with pytest.raises(ToolInputError, match="must be an integer, got float"):
            validate_int(5.0, "test")

    def test_rejects_string(self):
        with pytest.raises(ToolInputError, match="must be an integer"):
            validate_int("5", "test")

    def test_enforces_min_value(self):
        with pytest.raises(ToolInputError, match="must be >= 10"):
            validate_int(5, "test", min_value=10)

    def test_enforces_max_value(self):
        with pytest.raises(ToolInputError, match="must be <= 10"):
            validate_int(15, "test", max_value=10)


class TestValidateFloat:
    def test_accepts_int(self):
        assert validate_float(5, "test") == 5.0

    def test_accepts_float(self):
        assert validate_float(5.7, "test") == 5.7

    def test_rejects_bool(self):
        with pytest.raises(ToolInputError, match="must be a number, not a boolean"):
            validate_float(True, "test")

    def test_rejects_string(self):
        with pytest.raises(ToolInputError, match="must be a number"):
            validate_float("5.7", "test")

    def test_enforces_min_value(self):
        with pytest.raises(ToolInputError, match="must be >= 10.0"):
            validate_float(5.0, "test", min_value=10.0)

    def test_enforces_max_value(self):
        with pytest.raises(ToolInputError, match="must be <= 10.0"):
            validate_float(15.0, "test", max_value=10.0)


class TestValidateDict:
    def test_accepts_dict(self):
        d = {"a": 1, "b": 2}
        assert validate_dict(d, "test") == d

    def test_rejects_list(self):
        with pytest.raises(ToolInputError, match="must be a dict"):
            validate_dict([1, 2, 3], "test")

    def test_rejects_string(self):
        with pytest.raises(ToolInputError, match="must be a dict"):
            validate_dict("abc", "test")


class TestCandidateIds:
    def test_extracts_string_ids(self):
        assert candidate_ids(["a", "b", "c"]) == ["a", "b", "c"]

    def test_extracts_from_dicts(self):
        assert candidate_ids([{"item_id": "a"}, {"item_id": "b"}]) == ["a", "b"]

    def test_mixed_strings_and_dicts(self):
        assert candidate_ids(["a", {"item_id": "b"}, "c"]) == ["a", "b", "c"]

    def test_deduplicates_preserves_order(self):
        assert candidate_ids(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]

    def test_rejects_string_not_list(self):
        with pytest.raises(ToolInputError, match="must be a list or tuple"):
            candidate_ids("a")

    def test_rejects_dict_without_item_id(self):
        with pytest.raises(ToolInputError, match="must be an item_id string or dict"):
            candidate_ids([{"name": "a"}])

    def test_rejects_non_string_non_dict(self):
        with pytest.raises(ToolInputError, match="must be an item_id string or dict"):
            candidate_ids([123])


class TestCheckTopK:
    def test_accepts_valid_int(self):
        assert check_top_k(10) == 10

    def test_rejects_bool(self):
        with pytest.raises(ToolInputError, match="not a boolean.*limit/max_rows/top_k"):
            check_top_k(True)
        with pytest.raises(ToolInputError, match="not a boolean.*limit/max_rows/top_k"):
            check_top_k(False)

    def test_rejects_too_small(self):
        with pytest.raises(ToolInputError, match="must be >= 1"):
            check_top_k(0)

    def test_rejects_too_large(self):
        with pytest.raises(ToolInputError, match="must be <= 1000"):
            check_top_k(2000)
