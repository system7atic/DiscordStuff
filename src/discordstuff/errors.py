def describe_exception(exc: BaseException) -> str:
    """The exception's type plus its message, since some (e.g. httpx.ConnectError)
    have an empty message and would otherwise produce a blank alert."""
    message = str(exc).strip()
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__
