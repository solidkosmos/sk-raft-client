"""Console and transcript output shared by the SK-RAFT examples.

The tests all report the same way: a timestamped transcript on disk, a
filtered view of it on the console, a progress line every so often and a table
whose header is repeated as it scrolls. That machinery lives here so each test
file holds only its own logic.

Call :func:`configure` once at start-up to set the verbosity and the wording
of the warning cap, then :func:`open_log` to start the transcript and
:func:`close_log` when the run ends::

    configure(verbose=VERBOSE, warnings_on_console=5,
              warning_noun="adder errors",
              warning_hint="watch the FAIL column")
    open_log(LOG_PATH)
    try:
        stage("Connecting")
    finally:
        close_log()

Row formatting stays with the test that owns the columns; :class:`Table` only
takes care of repeating the header.
"""

from __future__ import annotations

import time

_log_file = None
_log_path: str | None = None
_verbose = False
_warnings_on_console = 5
_warning_noun = "warnings"
_warning_hint = ""
_warnings_shown = 0


# --------------------------------------------------------------------------- #
# Configuration and transcript lifecycle
# --------------------------------------------------------------------------- #
def configure(verbose: bool = False, warnings_on_console: int = 5,
              warning_noun: str = "warnings",
              warning_hint: str = "") -> None:
    """Set how much reaches the console.

    ``verbose`` lets :func:`detail` through. ``warnings_on_console`` caps how
    many :func:`warn` messages are shown before the rest are left to the
    transcript; ``warning_noun`` and ``warning_hint`` word the notice that
    announces the cap, e.g. ``"adder errors"`` and ``"watch the FAIL
    column"``.
    """
    global _verbose, _warnings_on_console, _warning_noun, _warning_hint
    global _warnings_shown
    _verbose = verbose
    _warnings_on_console = warnings_on_console
    _warning_noun = warning_noun
    _warning_hint = warning_hint
    _warnings_shown = 0


def open_log(path: str | None) -> None:
    """Start the transcript file. ``None`` disables the file."""
    global _log_file, _log_path
    _log_path = path
    if path:
        _log_file = open(path, "w", buffering=1)


def close_log() -> None:
    """Close the transcript file."""
    global _log_file
    if _log_file is not None:
        _log_file.close()
        _log_file = None


def log_path() -> str | None:
    """The transcript path in use, or ``None`` if logging is disabled."""
    return _log_path


def warnings_shown() -> int:
    """How many warnings have been raised so far in the run."""
    return _warnings_shown


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def emit(text: str, console: bool = True) -> None:
    """Write ``text`` to the transcript, and to the console unless muted."""
    if _log_file is not None:
        _log_file.write(f"{time.strftime('%H:%M:%S')} {text}\n")
    if console:
        print(text, flush=True)


def stage(message: str) -> None:
    """Announce a stage of the test run. Always shown."""
    emit(f"==> {message}")


def detail(message: str) -> None:
    """Per-item detail. Logged; shown only when configured verbose."""
    emit(f"    {message}", console=_verbose)


def warn(message: str) -> None:
    """A functional error. Always logged; shown until the console cap."""
    global _warnings_shown
    _warnings_shown += 1
    if _warnings_shown < _warnings_on_console:
        emit(f"  ! {message}")
    elif _warnings_shown == _warnings_on_console:
        emit(f"  ! {message}")
        if _log_path:
            notice = f"further {_warning_noun} go to {_log_path} only"
        else:
            notice = (f"further {_warning_noun} are not shown; the "
                      f"transcript is disabled")
        if _warning_hint:
            notice += f"; {_warning_hint}"
        emit(f"  ! {notice}")
    else:
        emit(f"  ! {message}", console=False)


# --------------------------------------------------------------------------- #
# Progress
# --------------------------------------------------------------------------- #
def elapsed_since(started: float) -> str:
    """Format an elapsed time compactly, e.g. ``1m04s`` or ``12.3s``."""
    seconds = time.perf_counter() - started
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"


def print_progress(done: int, total: int | None, count: int, label: str,
                   started: float) -> None:
    """Running summary, with a rate and an ETA when the total is known.

    ``count`` and ``label`` describe what went wrong so far, e.g. ``12`` and
    ``"broke the adder"``.
    """
    seconds = time.perf_counter() - started
    rate = done / seconds if seconds > 0 else 0.0
    line = (f"--- {done}"
            f"{f'/{total}' if total else ''} injections, "
            f"{count} {label}, {elapsed_since(started)} elapsed, "
            f"{rate:.1f} inj/s")
    if total and rate > 0:
        remaining = (total - done) / rate
        line += f", ~{int(remaining // 60)}m{int(remaining % 60):02d}s left"
    emit(line + " ---")


class Table:
    """A console table that repeats its header as the rows scroll past.

    The caller formats its own rows, so the columns stay with the test that
    defines them; this only decides when the header goes out again.
    """

    def __init__(self, header: str, header_every: int = 25):
        self.header = header
        self.header_every = header_every

    def row(self, index: int, text: str) -> None:
        """Emit one row, preceded by the header every ``header_every`` rows."""
        if (index - 1) % self.header_every == 0:
            emit(self.header)
        emit(text)
