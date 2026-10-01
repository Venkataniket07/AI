"""The memory games' size policies obey the `params_for` contract."""

import dataclasses

from core.timing import grid_size_and_xs, recall_length
from tests.helpers import assert_params_contract


@dataclasses.dataclass(frozen=True)
class _Recall:
    length: int


@dataclasses.dataclass(frozen=True)
class _Grid:
    size: int
    xs: int


def test_recall_length_contract():
    assert_params_contract(lambda level: _Recall(recall_length(level)), monotone_fields=["length"])


def test_grid_size_and_xs_contract():
    assert_params_contract(lambda level: _Grid(*grid_size_and_xs(level)), monotone_fields=["size", "xs"])
