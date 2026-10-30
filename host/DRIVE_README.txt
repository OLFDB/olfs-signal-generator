OLFs Signal Generator - native console tools
============================================

This read-only USB drive is stored in the dongle's firmware flash.
No Python, .NET or Java runtime is required. The applications control the
first CDC interface (OLF Shell). The second CDC interface carries logs.

Files:
  OLF-WIN.EXE  Windows 10/11, x64
  OLF-WARM.EXE Windows ARM64, native
  OLF-LX64     Linux x86_64, statically linked
  OLF-LARM     Linux ARM64/aarch64, statically linked
  OLF-MAC      macOS 11+, universal Intel + Apple Silicon
  OLFCTL.C     Client source code, SPDX-License-Identifier: Apache-2.0
  SHA256.TXT  SHA-256 hashes of the binaries
  LICENSE.TXT Client and linked runtime license notices
  BUILD.TXT   Build information and source/binary hashes

Copy the matching program to your computer before running it. No automatic
execution or installer is used. Close CoolTerm/other terminals on the shell
port before opening the client. USB CDC drivers come with current OSes.

Windows (PowerShell, after copying OLF-WIN.EXE; use OLF-WARM.EXE on ARM64):
  .\OLF-WIN.EXE --list
  .\OLF-WIN.EXE --port COM7 status
  .\OLF-WIN.EXE --port COM7

macOS (Terminal, after copying OLF-MAC):
  chmod +x OLF-MAC
  ./OLF-MAC --list
  ./OLF-MAC --port /dev/cu.usbmodemXXXX status
  ./OLF-MAC --port /dev/cu.usbmodemXXXX

Linux (terminal, after copying the matching binary):
  chmod +x OLF-LX64
  ./OLF-LX64 --list
  ./OLF-LX64 --port /dev/ttyACM0 status
  ./OLF-LX64 --port /dev/ttyACM0
  Use OLF-LARM instead on ARM64. Your user needs access to the serial port
  (commonly membership in dialout or uucp; distribution dependent).

Windows binaries are unsigned. macOS uses an ad-hoc signature for Apple
Silicon compatibility, without a Developer ID/notarization. OS policy may
require allowing a locally trusted application.

The port examples must be replaced with the actual SHELL port. --list shows
candidate serial ports, not guaranteed matches for this device. The app does
not guess or open other devices automatically. DTR is enabled when opening.

Interactive examples (type quit to exit):
  status
  link off
  wave sine left
  freq 1000 left
  amp 25 left
  wave triangle right
  freq 2000 right
  start
  stop
  link on
  gpio_app led on

The optional "gen" prefix is automatically added to generator commands.
Other Zephyr shell commands pass through unchanged. Use --help for syntax.
Rate (44.1/48/96 kHz) and bit depth (16/24 bit) are selected in the computer's
audio settings / recording app, not independently through the serial port.

Copying files and audio share USB bandwidth. For audio measurements, finish
copying the tools first. Applications on this drive update with the firmware.
