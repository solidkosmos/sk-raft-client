"""SEM detection test: does the SEM notice upsets injected while it was frozen?

Every stage waits for Enter, so you step through the test by hand. While it
waits, anything the SEM prints on the UART is shown live.

  1. Program the design. The SEM is isolated and its clock is frozen.
  2. Release the isolation, then start the clock. The SEM boots. Send I, then
     S, and read the SEM's status from the UART.
  3. Send I, isolate the SEM, freeze its clock.
  4. Inject 10 random CRAM upsets into pblock_1 while the SEM is cut off
     and frozen. No logic sits there, so the SEM and the UART are not
     touched; the SEM still sees the upsets, because its ECC and CRC
     cover whole frames.
  5. Release the isolation, start the clock, send O, and read the UART to see
     whether the SEM reports the upsets.
  6. Reprogram the device to clear the upsets.

BSCAN registers in the design:
  USER1  clock enable   1 = SEM clock runs, 0 = frozen (powers up as 0)
  USER2  SEM isolation  write 1 = isolate, 0 = connect
                        read  = the real state (1 = isolated)

Order matters. The isolation is released BEFORE the clock is started: a SEM
that boots while cut off from the ICAP reads zeros and halts (HLT). And the
SEM is only isolated once it is idle (after the I> prompt), never while it is
running.
"""

from __future__ import annotations

import re
import time

import serial
import serial.tools.list_ports

from skraft import BscanPrimitive, Design, SkraftError, SkraftFpga, TargetMemory

SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
PART_NUMBER = "210183BFD452A"

design = Design(
    bit=r"C:\Users\mario\VHDL_PROJECTS\sem_test\sem_test.runs\impl_1"
        r"\sem_arbitration.bit",
    ebd=r"C:\Users\mario\VHDL_PROJECTS\sem_test\sem_test.runs\impl_1"
        r"\sem_arbitration.ebd",
    xdc=r"C:\Users\mario\Downloads\Basys-3-Master.xdc",
)

# The board's USB-UART, as a COM port (see Device Manager). 
# SEM monitor: 9600 8-N-1.
UART_PORT = "COM5"
UART_BAUD = 9600

# Select the memory & the pblock inside this memory.
TARGET_MEMORY    = TargetMemory.CRAM
TARGET_PBLOCK    = "pblock_1"
# Select the number of injections to perform in the 
# configured region.
INJECTION_NUMBER = 10

# Command that brings the SEM back after the injections:
# "O" (observe), or "R 00" to re-initialize it
RESTART_COMMAND = "O"

# Pause between characters sent to the SEM 
# (it reads them from a small FIFO)
CHAR_DELAY_S = 0.02
# A reply is over once the UART has been silent for this long...
QUIET_S = 1.0
# ...or after this long at most
BOOT_WAIT_S = 10.0
REPLY_WAIT_S = 5.0
DETECT_WAIT_S = 10.0
# How long to wait for the isolation to take effect
ISOLATE_TIMEOUT_S = 2.0

# BSCAN registers: (USER number, width in bits)
USER_CLK_EN = BscanPrimitive(1, 1)
USER_SEM_ISOLATE = BscanPrimitive(2, 1)

# Everything the SEM printed, in order. Stage 5 reads its reports from here.
transcript: list[str] = []

REPORT = re.compile(r"PA ([0-9A-F]{8})(.*?)(?:END|$)", re.S)
BIT = re.compile(r"WD ([0-9A-F]{2}) BT ([0-9A-F]{2})")


def watch_for_enter() -> None:
    input()

def print_uart_response(text: str) -> None:
    """
        Prints the UART response in the terminal. 

        Parameters:
            text (str): The plaintext to print. 
    """
    if text:
        transcript.append(text)
        print(text.replace("\r\n", "\n").replace("\r", "\n"), end="", flush=True)

def wait_before_next_stage(uart: serial.Serial, title: str) -> None:
    """
        Wait for the user to press enter to continue on the 
        next stage of the example. 

        Parameters:
            serial (serial.Serial): The UART communication 
                                    channel.
            title (str): The title of the current stage of 
                         the example.
    """
    print(f"\n=== {title} ===")
    print("Press Enter to continue.")
    watch_for_enter()
    print_uart_response(uart.read(256).decode(errors="replace"))

def open_uart() -> serial.Serial:
    """
        Open the UART communication channel, or produces 
        an exception if that is not possible. 

        Returns:
            serial.Serial: The opened UART channel.
    """
    try:
        return serial.Serial(UART_PORT, UART_BAUD, timeout=0.05)
    except serial.SerialException:
        ports = ", ".join(port.device for port in serial.tools.list_ports.comports())
        raise RuntimeError(f"cannot open {UART_PORT}. "
                           f"Ports found: {ports or 'none'}") from None


def uart_read(uart: serial.Serial, max_wait: float) -> str:
    """
        Reads the output from the UART communication channel.

        Parameters:
            serial (serial.Serial): The UART communication 
                                    channel.
            max_wait (float): The time to wait for the result
                              in seconds.
        Returns: 
            str: The output of the UART.
    """
    data = b""
    start = last = time.time()
    while time.time() - start < max_wait:
        chunk = uart.read(256)
        if chunk:
            data += chunk
            last = time.time()
        elif data and time.time() - last >= QUIET_S:
            break
    text = data.decode(errors="replace")
    print_uart_response(text)
    return text


# Send a command one character at a time, then read the reply
def uart_send_command(uart: serial.Serial, command: str,
                      max_wait: float = REPLY_WAIT_S) -> str:
    """
        Sends @command through the UART channel & returns the 
        reply produced from the execution of the command.

        Parameters:
            uart (serial.Serial): The UART communication 
                                    channel.
            command (str): The command to be sent.
            max_wait (float): The maximum time to wait in
                              seconds.
        Returns:
            str: The reply produced from the execution of 
                 the command. 
    """
    print_uart_response(
            uart.read(uart.in_waiting).decode(errors="replace")
    )
    print(f"\n> {command}")
    for char in command:
        uart.write(char.encode())
        uart.flush()
        time.sleep(CHAR_DELAY_S)

    sem_reply = uart_read(uart, max_wait)
    return sem_reply

def set_clock(dev, enabled: bool) -> None:
    """
        Configures the clock of the SEM Controller as gated (disabled),
        or not-gated (enabled).

        Parameters: 
            dev (FpgaDevice): The FPGA device, for the communication 
                              to the BSCAN registers.
            enabled (bool): Whether the clock of the SEM Controller
                            should be gated. If True, the clock is
                            gated, otherwise, is functional.
    """
    dev.write_bscan(USER_CLK_EN, 1 if enabled else 0)

def is_isolated(dev) -> bool:
    """
        Determines whether the SEM Controller is in isolated mode.

        Parameters: 
            dev (FpgaDevice): The FPGA device, for the communication 
                              to the BSCAN registers. 
        Returns:
            bool: Whether the SEM Controller is in isolation mode.
            True, if this is the case, otherwise False. 
    """
    return bool(int.from_bytes(dev.read_bscan(USER_SEM_ISOLATE), "big") & 1)

def wait_for_isolation_setting_to_apply(dev, expected: bool) -> bool:
    """
        Waits for the isolation setting for the SEM Controller to 
        be applied. 

        Parameters:
            dev (FpgaDevice): The FPGA device, for the communication
                              to the BSCAN registers.
            expected (bool): The isolation setting that is 
                             expected to be applied.
        Returns: 
            bool: Whether the setting were applied. True 
            if applied, otherwise, False.
    """
    deadline = time.time() + ISOLATE_TIMEOUT_S
    while time.time() < deadline:
        if is_isolated(dev) == expected:
            return False 
        time.sleep(0.01)    
    return True

def set_isolation(dev, isolate_en: bool) -> None:
    """
        Configures the SEM Controller to be in isolation mode,
        by writting the corresponding value into the USER2 
        BSCAN register. 

        After the setting is set, it waits until the new 
        configuration to be applied before returning. 

        Parameters: 
            dev (FpgaDevice): The FPGA device, for the communication
                              to the BSCAN registers. 
            isolate_en (bool): Whether to configure the SEM 
                               Controller in isolation mode.
                               if isolate_en = True, the isolation
                               is applied, otherwise, the isolation
                               is disabled (if previously enabled).
    """
    dev.write_bscan(USER_SEM_ISOLATE, 1 if isolate_en else 0)

    applied = wait_for_isolation_setting_to_apply(dev, isolate_en)

    if not applied:
        expected_state = "isolated" if isolate_en else "connected"
        raise RuntimeError(f"the SEM did not become {expected_state} within "
                           f"{ISOLATE_TIMEOUT_S} s (is it idle?)")

def sem_state(uart: serial.Serial) -> str | None:
    """
        Parses the State Change (SC) value after the 
        execution of an S (status report) command. 
        Possible values are, 00 = idle, 02 = observation.

        Parameters:
            uart (serial.Serial): The uart communication
                                  channel. 
        Returns:
            str: If the SC value is available.
            None: Otherwise.
    """
    reply = uart_send_command(uart, "S")

    sc_regex = re.search(r"SC ([0-9A-F]{2})", reply)
    if sc_regex:
        sc_value = sc_regex.group(1)
        return sc_value
    else:
        return None 

def parse_reports(report: str) -> set[tuple[int, int, int]]:
    """
        Parses the report produced by the SEM Controller. Essentially
        printing the Frame Address (FAR), word and bit where the 
        scrubbing found an upset.

        Parameters:
            report (str): The report produced from the SEM Controller.
        Returns:
            set[tuple[int, int, int]]: All the FAR, WORD, BIT found 
                                       during the scrubbing session.
    """
    sites = set()
    for far, body in REPORT.findall(report):
        for word, bit in BIT.findall(body):
            sites.add((int(far, 16), int(word, 16), int(bit, 16)))
    return sites

# Which injected bits did the SEM report?
def print_detection(injected: list[tuple[int, int, int]],
                    found: set[tuple[int, int, int]], text: str) -> None:
    

    caught = sum(1 for site in injected if site in found)
    print(f"\nThe SEM reported {caught} of {len(injected)} injected bits.")
    # BLK is the FAR's block type: 0 = configuration frames, 1 = BRAM content
    print("     #  FAR       WORD  BIT  BLK  REPORTED")
    for n, site in enumerate(injected, 1):
        far, word, bit = site
        print(f"{n:>6}  {far:08x}  {word:>4}  {bit:>3}  {(far >> 23) & 7:>3}  "
              f"{'yes' if site in found else 'NO'}")
    extra = found - set(injected)
    if extra:
        print(f"{len(extra)} reported location(s) were not injected "
              f"(see the log above).")
    if "HLT" in text:
        print("The SEM halted (HLT).")


def report(label: str, ok: bool) -> None:
    print(f"\n[{'OK' if ok else 'MISSING'}] {label}")

def main() -> None:
    print("SEM detection test")
    try:
        with open_uart() as uart, \
             SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client, \
             client.attach(PART_NUMBER) as dev:
            # ------------------------------------------------------------- #
            # Stage 1: program. The SEM starts frozen (clock off) and is
            # isolated before it is ever started.
            # ------------------------------------------------------------- #
            wait_before_next_stage(
                    uart, 
                    "Stage 1: program the design, SEM isolated and frozen",
            )

            dev.uploadDesignToServer(design)
            dev.programFPGA()

            print(f"Programmed {PART_NUMBER}.")
            set_clock(dev, False)
            set_isolation(dev, True)
            print("SEM frozen and isolated.")

            # ------------------------------------------------------------- #
            # Stage 2: bring the SEM up. Connect it to the ICAP first, then
            # start its clock, so it boots against the real configuration.
            # ------------------------------------------------------------- #
            wait_before_next_stage(
                    uart, 
                    "Stage 2: release isolation, start the clock, send I and S",
            )

            set_isolation(dev, False)
            set_clock(dev, True)

            print("SEM running. Waiting for its boot report...")
            boot = uart_read(uart, BOOT_WAIT_S)
            report("boot finished (INIT OK, SC 02)",
                   "INIT OK" in boot and "SC 02" in boot)

            idle = uart_send_command(uart, "I")
            report("SEM idle (I> prompt)", "I>" in idle)
            status = uart_send_command(uart, "S")
            report("SEM printed its status (SC ..)", "SC " in status)

            # ------------------------------------------------------------- #
            # Stage 3: idle the SEM, cut it off, freeze it.
            # ------------------------------------------------------------- #
            wait_before_next_stage(
                    uart, 
                    "Stage 3: send I, isolate, freeze the clock",
            )

            # Once idle the SEM ignores I, so only send it if S says the SEM
            # is not idle yet.
            if sem_state(uart) == "00":
                print("\nSEM already idle.")
            else:
                uart_send_command(uart, "I")
                if sem_state(uart) != "00":
                    raise RuntimeError("the SEM did not confirm it is idle; "
                                       "not isolating a running SEM")
            set_isolation(dev, True)
            set_clock(dev, False)
            print("\nSEM idle, isolated and frozen.")

            # ------------------------------------------------------------- #
            # Stage 4: inject while nothing else touches the configuration.
            # ------------------------------------------------------------- #
            wait_before_next_stage(uart, f"Stage 4: inject {INJECTION_NUMBER} random upsets into "
                      f"{TARGET_PBLOCK}")
            print("     #  FAR       WORD  BIT")
            injected: list[tuple[int, int, int]] = []
            for n in range(1, INJECTION_NUMBER + 1):
                hit = dev.inject_random(TARGET_MEMORY, pblock=TARGET_PBLOCK)
                injected.append((hit.far, hit.word_index, hit.bit_index))
                print(f"{n:>6}  {hit.far:08x}  {hit.word_index:>4}  "
                      f"{hit.bit_index:>3}")

            # ------------------------------------------------------------- #
            # Stage 5: bring the SEM back and see whether it notices.
            # ------------------------------------------------------------- #
            wait_before_next_stage(uart, f"Stage 5: release isolation, start the clock, "
                      f"send {RESTART_COMMAND}")
            set_isolation(dev, False)
            set_clock(dev, True)
            print("SEM running.")
            mark = len(transcript)
            uart_send_command(uart, RESTART_COMMAND, DETECT_WAIT_S)
            found = parse_reports("".join(transcript[mark:]))
            # A detect-only SEM goes idle after a report. Send the command
            # again until every injected bit is found or nothing new comes.
            # A SEM that corrects stays in observation, so just wait for more.
            for _ in range(2 * INJECTION_NUMBER):
                if set(injected) <= found:
                    break
                known = len(found)
                if sem_state(uart) == "00":
                    uart_send_command(uart, RESTART_COMMAND, DETECT_WAIT_S)
                else:
                    uart_read(uart, DETECT_WAIT_S)
                found = parse_reports("".join(transcript[mark:]))
                if len(found) == known:
                    break
            print_detection(injected, found, "".join(transcript[mark:]))

            # ------------------------------------------------------------- #
            # Stage 6: clear the upsets.
            # ------------------------------------------------------------- #
            uart_send_command(uart, "Stage 6: reprogram to clear the upsets")
            dev.programFPGA()
            print("Reprogrammed.")

    except KeyboardInterrupt:
        print("Interrupted. Reprogram before running anything else that "
              "expects a clean configuration.")
        return
    except (SkraftError, RuntimeError, serial.SerialException) as error:
        print(f"\nStopped: {error}")
        return
    print("\nSEM detection test done.")


if __name__ == "__main__":
    main()
 
