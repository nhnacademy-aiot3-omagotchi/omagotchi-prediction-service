"""예외 메시지·소스 코드·지역 변수를 제외한 오류 호출 위치."""

from collections import deque
from pathlib import PurePath

MAX_CAUSES = 4
MAX_FRAMES = 12
MAX_CHARACTERS = 4096
TRUNCATED = "\n[truncated]"


def format_error_stack_trace(failure: BaseException) -> str:
    """원인별 예외 종류·모듈·함수·파일명·줄 번호만 포함한 중앙 로그 요약."""
    lines: list[str] = []
    current: BaseException | None = failure
    for depth in range(MAX_CAUSES):
        if current is None:
            break
        prefix = "Caused by: " if depth else ""
        lines.append(f"{prefix}{type(current).__module__}.{type(current).__qualname__}")
        frames: deque[str] = deque(maxlen=MAX_FRAMES)
        traceback = current.__traceback__
        frame_count = 0
        while traceback is not None:
            code = traceback.tb_frame.f_code
            module = traceback.tb_frame.f_globals.get("__name__", "unknown")
            # 파일의 절대 경로와 실행 줄의 원문 제외
            frames.append(
                f"  at {module}.{code.co_name}"
                f"({PurePath(code.co_filename).name}:{traceback.tb_lineno})"
            )
            frame_count += 1
            traceback = traceback.tb_next
        # Java와 동일하게 예외가 발생한 안쪽 호출부터 표시
        lines.extend(reversed(frames))
        if frame_count > MAX_FRAMES:
            lines.append("  [frames truncated]")
        current = current.__cause__ or (
            None if current.__suppress_context__ else current.__context__
        )
    if current is not None:
        lines.append("[causes truncated]")
    summary = "\n".join(lines)
    if len(summary) > MAX_CHARACTERS:
        return summary[:MAX_CHARACTERS - len(TRUNCATED)] + TRUNCATED
    return summary
