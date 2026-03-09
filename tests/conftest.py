"""Shared pytest fixtures for the picsl_greedy test suite."""

import os
import pytest


@pytest.fixture(scope="session")
def data_root():
    """Return absolute path to the greedy test data directory.

    Resolved in order:
    1. ``GREEDY_TEST_DATA_DIR`` environment variable.
    2. Relative sibling path ``../../greedy/testing/data`` (works when both
       repos are checked out side-by-side as ``greedy/`` and
       ``greedy_python/``).

    The fixture calls ``pytest.skip`` if the directory cannot be found so
    that individual tests are skipped rather than erroring out.
    """
    env = os.environ.get("GREEDY_TEST_DATA_DIR")
    if env:
        candidate = os.path.abspath(env)
    else:
        candidate = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "greedy", "testing", "data")
        )

    if not os.path.isdir(candidate):
        pytest.skip(
            f"Test data directory not found: {candidate!r}. "
            "Set the GREEDY_TEST_DATA_DIR environment variable to the "
            "greedy/testing/data directory."
        )
    return candidate
