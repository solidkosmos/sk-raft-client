# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""
Helpers for main.py: the UART of the SEM monitor and the parsing of the
SEM reports and status.

  Upset            the location of one injected upset (FAR, word, bit)
  SemUart          reads the SEM UART in a background thread, sends
                   commands
  print_reports    shows which injected bits the SEM reported
  status_text      names the SEM status bits that are set
  repeated_report  finds a SEM report that repeats (correction loop)
"""

from __future__ import annotations

import re
import threading
import time
from collections import Counter
from dataclasses import dataclass

import serial

# A SEM report: the frame address (PA), then lines "WD <word> BT <bit>".
# PA has 8 hex digits on 7 series and 7 on UltraScale.
REPORT = re.compile(r"PA ([0-9A-F]{7,8})(.*?)(?:END|$)", re.DOTALL)
BIT = re.compile(r"WD ([0-9A-F]{2}) BT ([0-9A-F]{2})")


@dataclass(frozen=True)
class Upset:
    """The location of one injected upset."""

    far: int
    word: int
    bit: int


class SemUart:
    """
    The UART of the SEM monitor.

    A background thread reads the UART and shows each SEM line after
    "  SEM| ". The text stays in a buffer until read() takes it. The
    thread drops the received bytes while muted is True (until the first
    flush()): the UART sends random bytes while the FPGA is programmed.

    Parameters:
        port (str): The COM port.
        quiet_s (float): A reply is complete when the UART is silent for
            this time, in seconds.
    """

    def __init__(self, port: str, quiet_s: float = 1.0) -> None:
        self.uart = serial.Serial(port, 9600, timeout=0.05)
        self.quiet_s = quiet_s
        self.text = ""
        self.line = ""
        self.last_rx = time.time()
        self.muted = True
        self.lock = threading.Lock()
        threading.Thread(target=self._receive, daemon=True).start()

    def _receive(self) -> None:
        """Read the UART and show the lines (thread)."""
        while True:
            chunk = self.uart.read(256).decode(errors="replace")
            with self.lock:
                if self.muted:
                    continue
                if chunk:
                    # The SEM ends its lines with CR, LF or CR LF
                    chunk = chunk.replace("\r\n", "\n").replace("\r", "\n")
                    self.text += chunk
                    self.last_rx = time.time()
                    *lines, self.line = (self.line + chunk).split("\n")
                    for text in lines:
                        if text:
                            print(f"  SEM| {text}", flush=True)
                elif self.line and time.time() - self.last_rx >= self.quiet_s:
                    # A prompt (O>, I>) has no line end
                    print(f"  SEM| {self.line}", flush=True)
                    self.line = ""

    def flush(self) -> None:
        """Drop all the received text, and show the new text again."""
        with self.lock:
            self.uart.reset_input_buffer()
            self.text = ""
            self.line = ""
            self.muted = False

    def read(self, max_wait_s: float = 10.0) -> str:
        """
        Wait until the SEM is silent for quiet_s, and take the text.

        Parameters:
            max_wait_s (float): The maximum time to wait, in seconds.

        Returns:
            str: The text that the SEM sent since the last read().
        """
        start = time.time()
        while time.time() - start < max_wait_s:
            time.sleep(0.1)
            if self.text and time.time() - self.last_rx >= self.quiet_s:
                break
        with self.lock:
            text, self.text = self.text, ""
        return text

    def wait_for(self, marker: str, max_wait_s: float = 10.0) -> str:
        """
        Wait until the SEM sends marker, then read until it is silent.

        Parameters:
            marker (str): The text to wait for, for example "O>".
            max_wait_s (float): The maximum time to wait, in seconds.

        Returns:
            str: The text that the SEM sent since the last read(). It does
                not hold marker if the SEM did not send it in max_wait_s.
        """
        start = time.time()
        while marker not in self.text and time.time() - start < max_wait_s:
            time.sleep(0.1)
        return self.read(self.quiet_s)

    def send(self, command: str) -> str:
        """
        Send a command to the SEM and read the reply.

        The SEM reads the command from a small FIFO. Thus the method sends
        one character at a time.

        Parameters:
            command (str): The command, for example "O" or "R 00".

        Returns:
            str: The text that the SEM sent, with the reply.
        """
        print(f"> {command}")
        for char in command:
            self.uart.write(char.encode())
            time.sleep(0.02)
        return self.read()


def status_text(status: int, names: tuple[str, ...], fatal: int) -> str:
    """
    Make a text with the names of the SEM status bits that are set.

    Parameters:
        status (int): The SEM status bits.
        names (tuple[str, ...]): The names of the status bits, bit 0 first.
        fatal (int): The mask of the state bits. All of them set is the
            fatal error state.

    Returns:
        str: The names of the set bits, with "idle" first if no state bit
            is set. "FATAL" for the fatal error state.
    """
    if status & fatal == fatal:
        return "FATAL (all state bits set)"
    names_set = [name for bit, name in enumerate(names)
                 if status & (1 << bit)]
    if not status & fatal:
        names_set.insert(0, "idle")
    return ", ".join(names_set)


def print_reports(upsets: list[Upset], text: str, show: bool,
                  total: bool = True) -> int:
    """
    Show which injected bits the SEM reported.

    The frame address (PA) in a SEM report can be different from the FAR
    of SK-RAFT. Thus a report matches an injected bit if the word and the
    bit are the same.

    Parameters:
        upsets (list[Upset]): The injected upsets.
        text (str): The UART text of the SEM.
        show (bool): True to show a line for each upset.
        total (bool): True to show the number of reported bits.

    Returns:
        int: The number of injected bits that the SEM reported.
    """
    # (word, bit) -> the PAs of the reports with this word and bit
    # A report shows each bit two times (before and after COR)
    reported: dict[tuple[int, int], list[str]] = {}
    for pa, body in REPORT.findall(text):
        for word, bit in dict.fromkeys(BIT.findall(body)):
            reported.setdefault((int(word, 16), int(bit, 16)), []).append(pa)

    caught = 0
    if show:
        print("\n    FAR       WORD  BIT  REPORTED")
    for upset in upsets:
        pas = reported.get((upset.word, upset.bit))
        result = f"yes, PA {pas.pop(0)}" if pas else "NO"
        caught += result != "NO"
        if show:
            print(f"    {upset.far:08x}  {upset.word:>4}  {upset.bit:>3}"
                  f"  {result}")
    if show:
        for (word, bit), pas in reported.items():
            for pa in pas:
                print(f"    reported, not injected: PA {pa} word {word} "
                      f"bit {bit}")
    if total:
        print(f"The SEM reported {caught} of {len(upsets)} injected bits.")
    return caught


def repeated_report(text: str, limit: int) -> str | None:
    """
    Find a SEM report that the SEM sent limit times or more.

    The same report (same PA, word and bit) again and again means that the
    SEM is stuck in a correction loop: its correction does not remove the
    error.

    Parameters:
        text (str): The UART text of the SEM.
        limit (int): The number of identical reports that is a loop.

    Returns:
        str | None: The repeated report as "PA <pa> <bits>", or None if no
            report repeats limit times.
    """
    # A report shows each bit two times (before and after COR)
    reports = Counter(
        (pa, tuple(dict.fromkeys(BIT.findall(body))))
        for pa, body in REPORT.findall(text)
    )
    for (pa, bits), count in reports.items():
        if count >= limit:
            words = ", ".join(f"WD {word} BT {bit}" for word, bit in bits)
            return f"PA {pa} {words} ({count} times)"
    return None
