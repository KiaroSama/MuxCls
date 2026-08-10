"""Shared fixtures.

Four test modules drive interactive prompts, and each had its own copy of the
same scripted-input helper. One copy here keeps them from drifting apart.
"""
import builtins

import pytest


@pytest.fixture
def answers(monkeypatch):
    """Feed a scripted sequence of answers to `input()`.

    Running out is an error rather than a hang: a prompt the test did not expect
    means the flow took a branch the test was not describing, and that is worth
    failing on.
    """
    def script(*values):
        queue = list(values)

        def fake_input(_prompt=""):
            if not queue:
                raise AssertionError("the code asked for more input than the test provided")
            return queue.pop(0)

        monkeypatch.setattr(builtins, "input", fake_input)

    return script
