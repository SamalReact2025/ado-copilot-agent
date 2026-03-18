"""Tests for utilities/validators.py"""

import pytest
from utilities.validators import validate_work_item_id


class TestValidateWorkItemId:
    def test_valid_integer(self):
        assert validate_work_item_id("42") == 42

    def test_valid_large_integer(self):
        assert validate_work_item_id("99999") == 99999

    def test_zero_raises(self):
        with pytest.raises(ValueError, match="positive"):
            validate_work_item_id("0")

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="positive"):
            validate_work_item_id("-5")

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError):
            validate_work_item_id("abc")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validate_work_item_id("")

    def test_float_string_raises(self):
        with pytest.raises(ValueError):
            validate_work_item_id("3.14")
