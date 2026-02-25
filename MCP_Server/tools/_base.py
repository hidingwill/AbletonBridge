"""Shared tool infrastructure: decorators, helpers, error formatting."""
import asyncio
import functools
import json
import logging

logger = logging.getLogger("AbletonBridge")


def _tool_handler(error_prefix: str):
    """Decorator that wraps tool functions with standard error handling.

    Runs the synchronous tool function in a thread pool via asyncio.to_thread()
    so it doesn't block the FastMCP async event loop during TCP/UDP I/O.

    All plain-string returns are wrapped in tool_success() for consistent JSON
    envelope. Returns that are already JSON (start with '{' or '[') pass through.

    Catches ValueError -> tool_error("Invalid input: ..."),
    ConnectionError -> tool_error("M4L bridge not available: ..."),
    Exception -> tool_error("Error {prefix}: ...")
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                result = await asyncio.to_thread(func, *args, **kwargs)
                if isinstance(result, str):
                    stripped = result.strip()
                    if stripped.startswith(("{", "[")):
                        return result  # already structured JSON
                    return tool_success(result)
                return result
            except ValueError as e:
                return tool_error(f"Invalid input: {e}")
            except ConnectionError as e:
                return tool_error(f"M4L bridge not available: {e}")
            except Exception as e:
                logger.error("Error %s: %s", error_prefix, e)
                return tool_error(f"Error {error_prefix}: {e}")
        return wrapper
    return decorator


def _m4l_result(result: dict) -> dict:
    """Extract result data from M4L response, or raise on error."""
    if result.get("status") == "success":
        return result.get("result", {})
    msg = result.get("message", "Unknown error")
    raise Exception(f"M4L bridge error: {msg}")


def tool_success(message: str, data: dict = None) -> str:
    """Create a standardized success response."""
    result = {"status": "ok", "message": message}
    if data:
        result["data"] = data
    return json.dumps(result)


def tool_error(message: str) -> str:
    """Create a standardized error response."""
    return json.dumps({"status": "error", "message": message})


def _report_progress(ctx, current: float, total: float, message: str = None):
    """Report progress from a sync tool thread.

    ctx.report_progress() is async, but tools run in asyncio.to_thread().
    This helper bridges the gap by scheduling the coroutine on the event loop.
    Fails silently if the event loop is unavailable.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                ctx.report_progress(current, total, message), loop
            )
    except Exception:
        pass  # progress is best-effort
