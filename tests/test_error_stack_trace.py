"""중앙 로그의 호출 위치 보존과 원문 제외 검증."""

from app.error_stack_trace import format_error_stack_trace


def test_keeps_locations_without_messages_or_source():
    # Given
    try:
        try:
            raise ValueError("email=private@example.test")
        except ValueError as cause:
            raise RuntimeError("token=private-token") from cause
    except RuntimeError as failure:
        # When
        summary = format_error_stack_trace(failure)

    # Then
    assert "builtins.RuntimeError" in summary
    assert "Caused by: builtins.ValueError" in summary
    assert "test_keeps_locations_without_messages_or_source(test_error_stack_trace.py:" in summary
    assert "private@example.test" not in summary
    assert "private-token" not in summary
    assert "raise " not in summary
    assert __file__ not in summary


def test_respects_suppressed_context():
    # Given
    try:
        try:
            raise ValueError("hidden-cause")
        except ValueError:
            raise RuntimeError("private-detail") from None
    except RuntimeError as failure:
        # When
        summary = format_error_stack_trace(failure)

    # Then
    assert "builtins.RuntimeError" in summary
    assert "ValueError" not in summary
    assert "private-detail" not in summary


def test_bounds_cyclic_causes():
    # Given
    first = RuntimeError("first-secret")
    second = ValueError("second-secret")
    first.__cause__ = second
    second.__cause__ = first

    # When
    summary = format_error_stack_trace(first)

    # Then
    assert summary.count("Caused by: ") == 3
    assert summary.endswith("[causes truncated]")
    assert "secret" not in summary


def test_limits_frames_to_the_innermost_calls():
    # Given
    def recurse(depth):
        if depth > 0:
            recurse(depth - 1)
        else:
            raise RuntimeError("private-detail")

    try:
        recurse(20)
    except RuntimeError as failure:
        # When
        summary = format_error_stack_trace(failure)

    # Then
    assert summary.count("  at ") == 12
    assert "[frames truncated]" in summary
    assert "private-detail" not in summary


def test_bounds_total_output_length():
    # Given
    oversized_error = type("LongError" * 1000, (RuntimeError,), {})
    failure = oversized_error("private-detail")

    # When
    summary = format_error_stack_trace(failure)

    # Then
    assert len(summary) == 4096
    assert summary.endswith("[truncated]")
    assert "private-detail" not in summary
