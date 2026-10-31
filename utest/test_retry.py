"""Unit tests for ParallelRunner.retry.RetryPolicy: argument validation, waits
and messages. How retries run on the threads is tested in test_parallel_runner."""

import pytest

from ParallelRunner.retry import DEFAULT_RETRY_DELAY, NO_RETRIES, RetryPolicy


def test_defaults_mean_one_attempt():
    policy = RetryPolicy.from_arguments()
    assert policy == NO_RETRIES
    assert (policy.attempts, policy.delay, policy.backoff) == (1, DEFAULT_RETRY_DELAY, 1.0)
    assert not policy.can_retry(1)


@pytest.mark.parametrize("value", [None, "", "None", "NONE"])
def test_not_given_values_use_the_defaults(value):
    assert RetryPolicy.from_arguments(value, value, value) == NO_RETRIES


def test_can_retry_until_the_last_attempt():
    policy = RetryPolicy(retries=2)
    assert [policy.can_retry(attempt) for attempt in (1, 2, 3)] == [True, True, False]


@pytest.mark.parametrize("value, retries", [(0, 0), (3, 3), ("2", 2), (" 4 ", 4)])
def test_call_retries_accepts_whole_numbers(value, retries):
    assert RetryPolicy.from_arguments(call_retries=value).retries == retries


@pytest.mark.parametrize("value", ["abc", -1, "-1", 1.5, "1.5", True])
def test_call_retries_rejects_anything_else(value):
    with pytest.raises(ValueError, match="expected a whole number of at least 0"):
        RetryPolicy.from_arguments(call_retries=value)


@pytest.mark.parametrize("value, seconds", [(0, 0), ("0", 0), ("500ms", 0.5), ("2s", 2), (1.5, 1.5)])
def test_retry_delay_uses_robot_time_format(value, seconds):
    assert RetryPolicy.from_arguments(retry_delay=value).delay == seconds


@pytest.mark.parametrize("value, message", [("soon", "Invalid retry_delay 'soon'"), ("-1", "can't be negative")])
def test_invalid_retry_delay(value, message):
    with pytest.raises(ValueError, match=message):
        RetryPolicy.from_arguments(retry_delay=value)


@pytest.mark.parametrize("value, backoff", [(1, 1.0), ("2", 2.0), (1.5, 1.5)])
def test_retry_backoff_accepts_numbers_from_one(value, backoff):
    assert RetryPolicy.from_arguments(retry_backoff=value).backoff == backoff


@pytest.mark.parametrize("value", [0.5, "0", "-2", "nan", "inf", "fast"])
def test_retry_backoff_rejects_anything_else(value):
    with pytest.raises(ValueError, match="retry_backoff"):
        RetryPolicy.from_arguments(retry_backoff=value)


def test_delay_is_fixed_without_backoff():
    policy = RetryPolicy(retries=3, delay=0.5)
    assert [policy.delay_after(attempt) for attempt in (1, 2, 3)] == [0.5, 0.5, 0.5]


def test_backoff_multiplies_the_delay_after_every_attempt():
    policy = RetryPolicy(retries=3, delay=1, backoff=2)
    assert [policy.delay_after(attempt) for attempt in (1, 2, 3)] == [1, 2, 4]


def test_messages():
    policy = RetryPolicy(retries=2, delay=1, backoff=2)
    assert policy.failed_message(1, "boom") == "Attempt 1 of 3 failed: boom; retrying in 1 second"
    assert policy.failed_message(2, "boom") == "Attempt 2 of 3 failed: boom; retrying in 2 seconds"
    assert policy.timed_out_message(1, "10 seconds") == (
        "Attempt 1 of 3 timed out after 10 seconds (call_timeout), it keeps running in the background; "
        "retrying in 1 second"
    )
    assert RetryPolicy(retries=1, delay=0).failed_message(1, "boom") == "Attempt 1 of 2 failed: boom; retrying now"
