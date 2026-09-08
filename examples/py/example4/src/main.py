"""TEST 4 - Essential-bit injection with a BSCAN adder self-test per upset.

Built on TEST 3: the EBD file is loaded, the device is programmed, and
``dev.essential_frames()`` provides the essential bit locations that
``dev.inject_at()`` is driven with. Two things are added.

First, the design under test is an adder reachable through three BSCAN USER
registers, so after every upset the adder is exercised and any wrong result is
reported as a warning:

    USER1    8 bits    operand A    (shifted in)
    USER2    8 bits    operand B    (shifted in)
    USER3   16 bits    result       (shifted out, A + B)

Second, two modes are chosen interactively at start-up:

* injection mode - ``random`` samples essential bits, ``exhaustive`` sweeps
  them all (as in TEST 3).
* fault mode - ``cumulative`` leaves every upset in place, so faults pile up.
  ``single`` injects, tests the adder, then injects the *same* bit again:
  flipping a bit twice restores it, so each test sees exactly one live fault.

``single`` + ``exhaustive`` is a per-bit characterisation of the design: each
essential bit is tested on its own, with the design clean in between.
"""

from __future__ import annotations

import random
import time

from skraft import InjectionArea
from skraft.datatypes import BscanPrimitive, DesignFiles, ServerPath
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga

NUMBER_OF_INJECTIONS = 1000
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

BITSTREAM = ServerPath("/home/embeddedcat/Desktop/bscan_tester.bit")
EBD = ServerPath("/home/embeddedcat/Desktop/bscan_tester.ebd")

WORD_BITS = 32

# Console pacing: a running summary every N injections, and the table header
# repeated every N rows so it stays in view while scrolling.
PROGRESS_EVERY = 50
HEADER_EVERY = 25

# Full timestamped transcript; None disables the file.
LOG_PATH = "test4_bscan_adder.log"

# True also prints the per-vector detail on the console.
VERBOSE = False

# How many failing vectors are spelled out on the console before the warnings
# are left to the log alone. Once the design is broken every later injection
# fails too, and those warnings drown the table; the row's FAIL n/N column
# still reports every one of them.
WARNINGS_ON_CONSOLE = 5

# The adder's BSCAN USER registers.
USER_A = BscanPrimitive(1, 8)        # operand A, shifted in
USER_B = BscanPrimitive(2, 8)        # operand B, shifted in
USER_RESULT = BscanPrimitive(3, 16)  # result, shifted out

# The operand pairs checked after each upset: one mid-range pair with
# alternating bit patterns (which also catches a stuck bit in either operand
# register, and sums to 0xFF), and the upper limit, the only pair that
# exercises the carry out of bit 7.
ADDER_TEST_VECTORS = (
    (0x5A, 0xA5),  # 90 + 165 = 255
    (0xFF, 0xFF),  # 255 + 255 = 510, carry into bit 8
)

TOTAL_VECTORS = len(ADDER_TEST_VECTORS)
RESULT_MASK = (1 << USER_RESULT.size_in_bits) - 1

TABLE_HEADER = ("     #  FAR         WORD  BIT  ADDER     ELAPSED")

_log_file = None
_warnings_shown = 0


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def open_log() -> None:
    """Start the transcript file, if one is configured."""
    global _log_file
    if LOG_PATH:
        _log_file = open(LOG_PATH, "w", buffering=1)


def close_log() -> None:
    """Close the transcript file."""
    global _log_file
    if _log_file is not None:
        _log_file.close()
        _log_file = None


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
    """Per-vector / per-correction detail. Logged; shown only if VERBOSE."""
    emit(f"    {message}", console=VERBOSE)


def warn(message: str) -> None:
    """A functional error. Always logged; shown until the console cap."""
    global _warnings_shown
    _warnings_shown += 1
    if _warnings_shown < WARNINGS_ON_CONSOLE:
        emit(f"  ! {message}")
    elif _warnings_shown == WARNINGS_ON_CONSOLE:
        emit(f"  ! {message}")
        emit(f"  ! further adder errors go to "
             f"{LOG_PATH or 'nowhere - LOG_PATH is disabled'} only; "
             f"watch the FAIL column")
    else:
        emit(f"  ! {message}", console=False)


def elapsed_since(started: float) -> str:
    """Format an elapsed time compactly, e.g. ``1m04s`` or ``12.3s``."""
    seconds = time.perf_counter() - started
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"


def print_row(index: int, far: int, word_index: int, bit_index: int,
              failures: int, started: float) -> None:
    """One table row per injection, with the header repeated periodically."""
    if (index - 1) % HEADER_EVERY == 0:
        emit(TABLE_HEADER)
    verdict = f"FAIL {failures}/{TOTAL_VECTORS}" if failures else "ok"
    emit(f"{index:>6}  {far:#010x}  {word_index:>4}  {bit_index:>3}  "
         f"{verdict:<8}  {elapsed_since(started):>7}")


def print_progress(done: int, total: int | None, faulty: int,
                   started: float) -> None:
    """Running summary, with a rate and an ETA when the total is known."""
    seconds = time.perf_counter() - started
    rate = done / seconds if seconds > 0 else 0.0
    line = (f"--- {done}"
            f"{f'/{total}' if total else ''} injections, "
            f"{faulty} broke the adder, {elapsed_since(started)} elapsed, "
            f"{rate:.1f} inj/s")
    if total and rate > 0:
        remaining = (total - done) / rate
        line += f", ~{int(remaining // 60)}m{int(remaining % 60):02d}s left"
    emit(line + " ---")


# --------------------------------------------------------------------------- #
# Essential bits
# --------------------------------------------------------------------------- #
def essential_bit_locations(dev) -> list[tuple[int, int, int]]:
    """Return every essential bit as an ``(far, word_index, bit_index)`` tuple.

    Built from the EBD-derived frames, so the EBD file must be loaded. On a
    large design this list can hold millions of entries; if that is a problem,
    consume ``iter_essential_bit_locations`` instead and only materialise what
    you need.
    """
    stage("Reading the essential frames (EBD) and locating essential bits")
    started = time.perf_counter()
    locations = list(iter_essential_bit_locations(dev))
    stage(f"{len(locations)} essential bits found in "
          f"{elapsed_since(started)}")
    return locations


def iter_essential_bit_locations(dev):
    """Lazily yield ``(far, word_index, bit_index)`` for each essential bit."""
    for frame in dev.essential_frames():
        for word_index, word in enumerate(frame.words):
            value = word.value
            if value == 0:
                continue  # no essential bit in this word
            for bit_index in range(WORD_BITS):
                if (value >> bit_index) & 1:
                    yield frame.far, word_index, bit_index


# --------------------------------------------------------------------------- #
# Adder self-test
# --------------------------------------------------------------------------- #
def adder_test_vectors():
    """Yield the operand pairs checked after each upset."""
    yield from ADDER_TEST_VECTORS


def read_adder(dev, a: int, b: int) -> int:
    """Apply operands ``a`` and ``b`` and return the adder's result.

    The operands are shifted into USER1 and USER2 with ``write_bscan``; the
    result is read from USER3 with ``read_bscan``, which shifts a dummy value
    through and leaves the register contents untouched.
    """
    dev.write_bscan(USER_A, a)
    dev.write_bscan(USER_B, b)
    return int.from_bytes(dev.read_bscan(USER_RESULT), "big") & RESULT_MASK


def test_adder(dev, context: str) -> int:
    """Test the adder over its input combinations, warning on each mismatch.

    ``context`` labels the warnings, e.g. the injection number. Returns the
    number of wrong results, so 0 means the design still works.
    """
    failures = 0
    for a, b in adder_test_vectors():
        expected = (a + b) & RESULT_MASK
        actual = read_adder(dev, a, b)
        if actual == expected:
            detail(f"{context}: A={a:#04x} B={b:#04x} -> {actual:#06x} ok")
        else:
            failures += 1
            warn(f"{context}: A={a:#04x} B={b:#04x} -> expected "
                 f"{expected:#06x}, got {actual:#06x} "
                 f"(differing bits {expected ^ actual:#06x})")
    return failures


def correct_upset(dev, far: int, word_index: int, bit_index: int) -> None:
    """Undo an upset by injecting the same bit a second time."""
    dev.inject_at(far, word_index, bit_index, InjectionArea.ESSENTIAL_CRAM)
    detail(f"corrected FAR={far:#010x} WORD_INDEX={word_index} "
           f"BIT_INDEX={bit_index}")


# --------------------------------------------------------------------------- #
# Injection campaigns
# --------------------------------------------------------------------------- #
def inject_random_essential(dev, injections: int, cumulative: bool) -> int:
    """Inject ``injections`` upsets at randomly chosen essential bits, testing
    the adder after each one.

    Uses ``essential_frames`` to know where the essential bits are and
    ``inject_at`` to hit them. When ``cumulative`` is false each upset is
    corrected after its test. Returns the number of upsets injected.
    """
    locations = essential_bit_locations(dev)
    if not locations:
        stage("No essential bits found - check that the EBD file matches "
              "the bitstream.")
        return 0

    stage(f"Random injection: {injections} upsets from {len(locations)} "
          f"essential bits, "
          f"{'cumulative' if cumulative else 'corrected after each test'}")
    started = time.perf_counter()

    faulty = 0
    first_failure = None

    for i in range(1, injections + 1):
        far, word_index, bit_index = random.choice(locations)
        detail(f"injection {i}: flipping FAR={far:#010x} "
               f"WORD_INDEX={word_index} BIT_INDEX={bit_index}")
        dev.inject_at(far, word_index, bit_index,
                      InjectionArea.ESSENTIAL_CRAM)

        failures = test_adder(dev, f"injection {i}")
        if failures:
            faulty += 1
            if first_failure is None:
                first_failure = i

        if not cumulative:
            correct_upset(dev, far, word_index, bit_index)

        print_row(i, far, word_index, bit_index, failures, started)
        if i % PROGRESS_EVERY == 0:
            print_progress(i, injections, faulty, started)

    report_functional_errors(faulty, injections, first_failure)
    return injections


def inject_exhaustive_essential(dev, cumulative: bool) -> int:
    """Inject one upset into every essential bit, once, testing the adder after
    each one.

    Same ``essential_frames`` -> ``inject_at`` path as the random variant, but
    it sweeps the whole set instead of sampling it. When ``cumulative`` is
    false each upset is corrected after its test. Returns the number of upsets
    injected.

    Cumulative sweeps flip every essential bit of the design by the end, so
    re-program the device afterwards before running any other test.
    """
    stage(f"Exhaustive injection over every essential bit, "
          f"{'cumulative' if cumulative else 'corrected after each test'}")
    started = time.perf_counter()

    injected = 0
    faulty = 0
    first_failure = None

    for far, word_index, bit_index in iter_essential_bit_locations(dev):
        injected += 1
        detail(f"injection {injected}: flipping FAR={far:#010x} "
               f"WORD_INDEX={word_index} BIT_INDEX={bit_index}")
        dev.inject_at(far, word_index, bit_index,
                      InjectionArea.ESSENTIAL_CRAM)

        failures = test_adder(dev, f"injection {injected}")
        if failures:
            faulty += 1
            if first_failure is None:
                first_failure = injected

        if not cumulative:
            correct_upset(dev, far, word_index, bit_index)

        print_row(injected, far, word_index, bit_index, failures, started)
        if injected % PROGRESS_EVERY == 0:
            print_progress(injected, None, faulty, started)

    stage(f"Swept {injected} essential bits in {elapsed_since(started)}")
    report_functional_errors(faulty, injected, first_failure)
    return injected


def report_functional_errors(faulty: int, injections: int,
                             first_failure: int | None) -> None:
    """Print the functional-error tally for a completed run."""
    stage(f"Injections that broke the adder: {faulty}/{injections}")
    if first_failure is None:
        stage("The adder answered correctly after every upset.")
    else:
        stage(f"First adder error appeared at injection {first_failure}.")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def ask_mode() -> str:
    """Ask for the injection mode until a valid answer is given."""
    while True:
        answer = input("Injection mode - [r]andom or [e]xhaustive? ").strip().lower()
        if answer in ("r", "random"):
            return "random"
        if answer in ("e", "exhaustive"):
            return "exhaustive"
        print("Please answer 'r' or 'e'.")


def ask_fault_mode() -> str:
    """Ask whether faults accumulate, until a valid answer is given."""
    while True:
        answer = input("Fault mode - [c]umulative or [s]ingle "
                       "(correct after each test)? ").strip().lower()
        if answer in ("c", "cumulative"):
            return "cumulative"
        if answer in ("s", "single"):
            return "single"
        print("Please answer 'c' or 's'.")


def main() -> None:
    print("TEST 4: essential-bit injection with a BSCAN adder self-test.")

    mode = ask_mode()
    fault_mode = ask_fault_mode()
    cumulative = fault_mode == "cumulative"

    open_log()
    started = time.perf_counter()
    try:
        stage(f"Run: {mode} injection, {fault_mode} faults, "
              f"{TOTAL_VECTORS} adder vectors per check")
        if LOG_PATH:
            stage(f"Full detail is being written to {LOG_PATH}")

        stage(f"Connecting to the SK-RAFT server at "
              f"{SK_RAFT_SERVER_IP}:{SK_RAFT_SERVER_PORT}")
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            stage(f"Connected, server version {client.version()}")

            stage(f"Reserving device {DEVICE}")
            with client.attach(DEVICE) as dev:
                stage("Loading the design files")
                dev.load(DesignFiles(bitstream=BITSTREAM, ebd=EBD))
                detail(f"bitstream: {BITSTREAM}")
                detail(f"EBD:       {EBD}")

                stage("Programming the device")
                dev.program()
                stage(f"Programmed {DEVICE}, {dev.essential_cram_bits} "
                      f"essential CRAM bits")

                # Golden run. A failure here means the USER register ids or
                # widths do not match the design, not an injected upset.
                stage("Baseline adder check")
                if test_adder(dev, "baseline"):
                    stage("TEST 4 aborted: the adder is already wrong before "
                          "any injection - check the USER register ids and "
                          "widths.")
                    return
                stage("Baseline passed")

                if mode == "random":
                    injected = inject_random_essential(dev,
                                                       NUMBER_OF_INJECTIONS,
                                                       cumulative)
                else:
                    injected = inject_exhaustive_essential(dev, cumulative)

                stage("Releasing the device and closing the connection")

        stage(f"TEST 4 done ({mode}, {fault_mode}): {injected} upsets "
              f"injected in {elapsed_since(started)}")
    except SkraftError as e:
        stage(f"TEST 4 failed: {e}")
    except KeyboardInterrupt:
        stage(f"TEST 4 interrupted after {elapsed_since(started)}")
    finally:
        close_log()


if __name__ == "__main__":
    main()
