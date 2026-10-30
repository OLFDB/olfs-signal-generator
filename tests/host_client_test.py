#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise the native POSIX client against a pseudo-terminal shell."""
import os
import select
import signal
import subprocess
import sys
import threading
import time


def exchange(binary, arguments, commands, stdin=None):
    master, slave = os.openpty()
    received = []
    errors = []

    def peer():
        try:
            pending = b""
            deadline = time.monotonic() + 10
            while len(received) < len(commands) and time.monotonic() < deadline:
                if not select.select([master], [], [], 0.1)[0]:
                    continue
                pending += os.read(master, 1024)
                while b"\r" in pending:
                    line, pending = pending.split(b"\r", 1)
                    received.append(line)
                    os.write(master, b"OK: " + line + b"\r\nuart:~$ ")
        except Exception as error:
            errors.append(error)

    thread = threading.Thread(target=peer)
    thread.start()
    try:
        process = subprocess.run([binary, "--port", os.ttyname(slave), *arguments],
                                 input=stdin, capture_output=True, timeout=12)
        thread.join(timeout=2)
        assert not thread.is_alive() and not errors, errors
        assert process.returncode == 0, (process.stderr, process.stdout)
        assert received == commands, (received, commands)
        assert b"OK:" in process.stdout
    finally:
        os.close(master)
        os.close(slave)


def main(binary):
    exchange(binary, ["freq", "1234", "left"], [b"gen freq 1234 left"])
    exchange(binary, ["gen", "status"], [b"gen status"])
    exchange(binary, [], [b"gen link off", b"gpio_app led on", b"gen stop"],
             b"link off\ngpio_app led on\nstop\nquit\n")
    master, slave = os.openpty()
    process = subprocess.Popen([binary, "--port", os.ttyname(slave)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        time.sleep(0.7)
        process.send_signal(signal.SIGINT)
        assert process.wait(timeout=2) == 0
    finally:
        if process.poll() is None:
            process.kill()
        os.close(master)
        os.close(slave)
    invalid = subprocess.run([binary, "--port", "/nonexistent/olf-test"], capture_output=True)
    assert invalid.returncode == 1
    print("Native client: PTY commands, interactive mode, passthrough, Ctrl+C and open errors passed")


if __name__ == "__main__":
    main(sys.argv[1])
