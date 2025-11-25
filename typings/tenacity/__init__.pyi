"""Type stubs for tenacity retry library."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar, overload

# Type variables for decorated functions
F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T")

# Base types for retry strategies (support combining with | and &)
class StopBaseT:
    def __or__(self, other: StopBaseT) -> StopBaseT: ...
    def __and__(self, other: StopBaseT) -> StopBaseT: ...

class WaitBaseT:
    def __or__(self, other: WaitBaseT) -> WaitBaseT: ...
    def __add__(self, other: WaitBaseT) -> WaitBaseT: ...

class RetryBaseT:
    def __or__(self, other: RetryBaseT) -> RetryBaseT: ...
    def __and__(self, other: RetryBaseT) -> RetryBaseT: ...

# Retry state
class RetryCallState:
    attempt_number: int
    outcome: Any
    next_action: Any
    idle_for: float
    start_time: float
    seconds_since_start: float
    retry_object: Retrying
    fn: Callable[..., Any] | None
    args: tuple[Any, ...]
    kwargs: dict[str, Any]

# Exception classes
class RetryError(Exception):
    last_attempt: Any

# Core retry decorator
@overload
def retry(func: F) -> F: ...

@overload
def retry(
    *,
    sleep: Callable[[int | float], None] = ...,
    stop: StopBaseT | None = ...,
    wait: WaitBaseT | None = ...,
    retry: RetryBaseT | None = ...,
    before: Callable[[RetryCallState], None] | None = ...,
    after: Callable[[RetryCallState], None] | None = ...,
    before_sleep: Callable[[RetryCallState], None] | None = ...,
    reraise: bool = ...,
    retry_error_cls: type[RetryError] = ...,
    retry_error_callback: Callable[[RetryCallState], Any] | None = ...,
) -> Callable[[F], F]: ...

# Retrying classes
class Retrying:
    def __init__(
        self,
        sleep: Callable[[int | float], None] = ...,
        stop: StopBaseT | None = ...,
        wait: WaitBaseT | None = ...,
        retry: RetryBaseT | None = ...,
        before: Callable[[RetryCallState], None] | None = ...,
        after: Callable[[RetryCallState], None] | None = ...,
        before_sleep: Callable[[RetryCallState], None] | None = ...,
        reraise: bool = ...,
        retry_error_cls: type[RetryError] = ...,
        retry_error_callback: Callable[[RetryCallState], Any] | None = ...,
    ) -> None: ...
    
    def __call__(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T: ...
    def wraps(self, fn: F) -> F: ...

class AsyncRetrying(Retrying):
    def __init__(
        self,
        sleep: Callable[[float], Awaitable[Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    
    def wraps(self, fn: F) -> F: ...

# Stop strategies
def stop_never() -> StopBaseT: ...
def stop_after_attempt(max_attempt_number: int) -> StopBaseT: ...
def stop_after_delay(max_delay: float) -> StopBaseT: ...
def stop_when_event_set(event: Any) -> StopBaseT: ...

# Wait strategies
def wait_none() -> WaitBaseT: ...
def wait_fixed(wait: float) -> WaitBaseT: ...
def wait_random(min: float, max: float) -> WaitBaseT: ...
def wait_incrementing(start: float, increment: float, max: float | None = ...) -> WaitBaseT: ...
def wait_exponential(
    multiplier: float = ...,
    max: float = ...,
    exp_base: float = ...,
    min: float = ...,
) -> WaitBaseT: ...
def wait_exponential_jitter(
    initial: float = ...,
    max: float = ...,
    exp_base: float = ...,
    jitter: float = ...,
) -> WaitBaseT: ...
def wait_random_exponential(
    multiplier: float = ...,
    max: float = ...,
    exp_base: float = ...,
) -> WaitBaseT: ...
def wait_chain(*waits: WaitBaseT) -> WaitBaseT: ...
def wait_combine(*waits: WaitBaseT) -> WaitBaseT: ...

# Retry strategies
def retry_if_exception_type(exception_types: type[BaseException] | tuple[type[BaseException], ...] = ...) -> RetryBaseT: ...
def retry_if_not_exception_type(exception_types: type[BaseException] | tuple[type[BaseException], ...]) -> RetryBaseT: ...
def retry_if_exception(predicate: Callable[[BaseException], bool]) -> RetryBaseT: ...
def retry_if_exception_cause_type(exception_types: type[BaseException] | tuple[type[BaseException], ...]) -> RetryBaseT: ...
def retry_if_result(predicate: Callable[[Any], bool]) -> RetryBaseT: ...
def retry_if_not_result(predicate: Callable[[Any], bool]) -> RetryBaseT: ...
def retry_unless_exception_type(exception_types: type[BaseException] | tuple[type[BaseException], ...]) -> RetryBaseT: ...
def retry_if_exception_message(
    message: str | None = ...,
    match: str | None = ...,
) -> RetryBaseT: ...
def retry_if_not_exception_message(
    message: str | None = ...,
    match: str | None = ...,
) -> RetryBaseT: ...
def retry_any(*retries: RetryBaseT) -> RetryBaseT: ...
def retry_all(*retries: RetryBaseT) -> RetryBaseT: ...

# Before/after callbacks
def before_nothing(retry_state: RetryCallState) -> None: ...
def before_log(logger: Any, log_level: int) -> Callable[[RetryCallState], None]: ...
def after_nothing(retry_state: RetryCallState) -> None: ...
def after_log(logger: Any, log_level: int) -> Callable[[RetryCallState], None]: ...
def before_sleep_nothing(retry_state: RetryCallState) -> None: ...
def before_sleep_log(logger: Any, log_level: int) -> Callable[[RetryCallState], None]: ...
