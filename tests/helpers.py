"""Shared test helpers."""

import dataclasses
from typing import Callable, Sequence


def assert_params_contract(params_for: Callable, monotone_fields: Sequence[str] = ()) -> None:
    """Check the `ParamsFor` contract: total on 1..10, clamps 0 and 99, frozen dataclass, fields non-decreasing."""
    results = [params_for(level) for level in range(1, 11)]
    for params in results:
        assert dataclasses.is_dataclass(params) and not isinstance(params, type)
        assert params.__dataclass_params__.frozen, "params must be a frozen dataclass"
    assert params_for(0) == results[0] and params_for(-5) == results[0]
    assert params_for(99) == results[-1]
    for field in monotone_fields:
        values = [getattr(p, field) for p in results]
        assert values == sorted(values), f"{field} must not decrease with level: {values}"
