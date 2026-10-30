# OLFs Signal Generator – nRF52840 Dongle / Open Bootloader

**[Entwicklerdokumentation mit Architektur- und Ablaufgrafiken](docs/index.html)** · Offline im Browser öffnen, mit Suche und PDF-Druckansicht.

Der reguläre Build verwendet wieder den originalen Nordic USB Open Bootloader.
MCUboot ist deaktiviert. MBR, originaler Bootloader, Settings und UICR werden
vom Anwendungsimage nicht beschrieben. Audiogenerator, zwei serielle Ports
und Tools-Laufwerk bleiben enthalten.

## Bauen

Board: **`nrf52840dongle/nrf52840`** (ohne `/bare`), nRF Connect SDK 3.2.1.
In nRF Connect for VS Code dieses Board wählen und Sysbuild aktivieren.

```sh
python3 scripts/build_firmware.py --pristine
python3 scripts/package_openbootloader.py
```

Nach dem Boardwechsel ist ein Pristine Build erforderlich. Für spätere Builds
genügt der erste Befehl ohne `--pristine`; anschließend das DFU-Paket neu erzeugen.
Der Paketbefehl benötigt `nrfutil` mit installiertem `nrf5sdk-tools`.

## Installation über USB

Da MCUboot hier noch nicht auf den Dongle geflasht wurde, ist für diese
Firmware kein SWD-Programmer erforderlich.

1. Dongle einstecken und RESET drücken: Die rote LED pulsiert.
2. In **nRF Connect for Desktop → Programmer** den Dongle auswählen.
3. **Add file**: `build/multi_cdc_vscode_ready/zephyr/zephyr.hex` öffnen.
4. **Write** ausführen. Danach startet die Anwendung.

Alternativ das Nordic-DFU-ZIP über die Kommandozeile übertragen:

```sh
nrfutil nrf5sdk-tools dfu usb-serial -pkg build/multi_cdc_dfu.zip -p PORT
```

`PORT` durch den Port des originalen Bootloaders ersetzen, beispielsweise
`/dev/cu.usbmodem…` oder `COM5`. Dieser unterscheidet sich von den beiden
Anwendungsports. Für weitere Updates wieder RESET drücken.

| Datei | Zweck |
|---|---|
| `build/multi_cdc_vscode_ready/zephyr/zephyr.hex` | Anwendungsimage für Programmer |
| `build/multi_cdc_dfu.zip` | Anwendungsupdate für Nordic USB-DFU |
| `build/olfs-openbootloader-bundle.zip` | Paket mit HEX, DFU-ZIP und Prüfergebnis |
| `build/openbootloader-verification.json` | Prüfung von Layout und Paketinhalt |

Die Anwendung startet bei `0x1000` und bleibt unter `0xe0000`. Es wird kein
Ersatz-Bootloader installiert. Der originale Open Bootloader erzwingt keine
Signaturprüfung; das DFU-Paket ist unsigniert und benötigt keinen privaten
Schlüssel. Die früheren MCUboot- und Secure-DFU-Builds sind unter `artifacts/`
archiviert und gehören nicht zu dieser Installation.
Weitere Details: [bootloader/README.md](bootloader/README.md).

## USB-Funktionen der Anwendung

Gerätename: **OLFs Signal Generator**. Hersteller: **eisenzelt.de**. USB-Kennung: **VID `0x16d0`, PID `0x1471`**.

- Audioeingang am Rechner: Stereo, 44,1 / 48 / 96 kHz, 16 oder 24 Bit.
- CDC 0: `OLF Shell` für Steuerung und Befehlsantworten.
- CDC 1: `OLF Logs` für separate Logausgaben.
- Schreibgeschütztes FAT12-Laufwerk `OLFS TOOLS` (512 KiB) mit nativen
  Konsolenapps, Quelltext, Anleitung und Lizenzinformationen.

macOS vergibt die `/dev/cu.usbmodem*`-Pfade selbst. Im Terminal DTR aktivieren.
Für Shell-History in CoolTerm Raw Mode und Emulate Special Keys aktivieren;
bei Darstellungsproblemen ein vollständiges VT100-Terminal verwenden.

## Audiogenerator über die Shell

```sh
gen status
gen link off
gen wave sine left
gen freq 1000 left
gen amp 25 left
gen wave triangle right
gen freq 2000 right
gen amp 40 right
gen start
gen stop right
gen link on
gen stop
```

- `gen wave sine|triangle|square [left|right|both]`: Signalform.
- `gen freq 1..20000 [left|right|both]`: Frequenz in Hz, ganzzahlig.
- `gen amp 0..100 [left|right|both]`: Spitzenamplitude in Prozent.
- `gen start [left|right|both]`, `gen stop [left|right|both]`: Signal oder Stille.
- `gen link on`: rechts übernimmt Einstellungen und Phase von links.
  Änderungen wirken gekoppelt immer auf beide Kanäle; alte rechte Werte
  werden überschrieben. `gen link off` erlaubt unabhängige Einstellungen.
- Ohne Kanalangabe werden beide Kanäle eingestellt. Im unabhängigen Modus
  werden dadurch die Phasen nicht synchronisiert.
- `gen status`: beide Kanäle, Kopplung, Host-Rate/Bittiefe und Paketzähler.

Vorgabe: gekoppelt, Sinus 1000 Hz, 25 % Amplitude, gestoppt. Einstellungen liegen
im RAM. Signaländerungen sind unmittelbar und können klicken. Dreieck und
Rechteck sind nicht bandbegrenzt und können bei hohen Frequenzen aliasen.

Samplerate und Bittiefe wählt die Audio-App bzw. unter macOS Audio-MIDI-Setup.
Beide Kanäle teilen sich dieses USB-Format. Der Rechner sieht den Generator als
Aufnahmegerät; zum Anhören in der Audio-App Monitoring einschalten.

| Rate | Samples je Kanal und ms | 16-Bit-Paket | 24-Bit-Paket |
|---|---:|---:|---:|
| 44,1 kHz | 44 oder 45 | 176 oder 180 Byte | 264 oder 270 Byte |
| 48 kHz | 48 | 192 Byte | 288 Byte |
| 96 kHz | 96 | 384 Byte | 576 Byte |

Ein Restakkumulator sorgt bei 44,1 kHz für exakt 44100 Samples je Sekunde. Die
Generatorphase bleibt über Paket-, Format- und Ratenwechsel erhalten.
Der Host überträgt Audio per USB IN; externe I2S-Hardware ist nicht erforderlich.

## GPIO und Logs

```sh
log status
log enable dbg gpio_app
gpio_app led on
gpio_app led off
log enable inf gpio_app
```

`gpio_app` steuert die grüne LED (P0.06, active-low) und loggt diese Aktionen.
Das Modul protokolliert nicht automatisch alle GPIO-Zugriffe. Logs erscheinen
auf dem zweiten CDC-Port; die Shell kann deren Filter bis zum Neustart ändern.

## Native Konsolenapps und Tools-Laufwerk

Die Programme benötigen zur Ausführung kein Python, Java oder .NET:

| Datei unter `host/dist/` | Plattform |
|---|---|
| `OLF-WIN.EXE` | Windows 10/11 x64 |
| `OLF-WARM.EXE` | Windows ARM64, nativ |
| `OLF-LX64` | Linux x86_64, statisch |
| `OLF-LARM` | Linux ARM64, statisch |
| `OLF-MAC` | macOS 11+, Intel und Apple Silicon |

Passendes Programm vom Laufwerk auf den Rechner kopieren. Auf macOS/Linux
bei Bedarf `chmod +x OLF-MAC` bzw. `OLF-LX64`/`OLF-LARM` ausführen.

```sh
./OLF-MAC --list
./OLF-MAC --port /dev/cu.usbmodemXXXX status
./OLF-MAC --port /dev/cu.usbmodemXXXX
```

`--list` zeigt Kandidaten. Den Shell-Port explizit auswählen und andere
Terminals zuvor trennen. Interaktiv funktionieren beispielsweise `freq 1000
left`, `amp 25`, `start`, `stop` und `quit`. `gen` wird bei Generatorbefehlen
ergänzt; andere Shell-Befehle werden unverändert übertragen. Samplerate und
Bittiefe bleiben Einstellungen der Audio-App.

Die Mac-Datei ist ad-hoc signiert, ohne Developer ID/Notarisierung; die
Windows-Datei ist nicht mit Authenticode signiert. Lokale Ausführungsrichtlinien
gelten weiterhin. Dateikopien teilen USB-/DMA-/CPU-Ressourcen mit Audio.

Das FAT-Image liegt konstant im Flash, wird nicht in RAM kopiert und nicht
zur Laufzeit beschrieben. Es wird mit der Firmware aktualisiert. Nach Änderungen
an `host/olfctl.c` müssen die Clients neu gebaut werden:

```sh
python3 host/build_clients.py --zig /pfad/zu/zig
python3 scripts/build_firmware.py
```

Client-Build: macOS/Xcode und Zig 0.14.1 für Windows/Linux-Cross-Compilation.
Quelltext- und Binärhashes werden vor dem Erzeugen des Laufwerks geprüft.
Weitere Hinweise: `host/DRIVE_README.txt`.

## Projektlokale SDK-Anpassungen

- `cmake/nrf52840_iso_in.cmake`: vollständiger ISO-Puffer für IN (1023 Byte),
  ISO OUT gesperrt. CDC-OUT bleibt verfügbar. Stereo 96 kHz/24 Bit braucht
  576 Byte/ms; der unveränderte Treiber bietet nur 511 Byte pro Richtung.
- `cmake/uac2_formats.cmake`: zwei USB-Alternate-Settings für 16/24 Bit auf
  demselben Audio-Stream. Das SDK bietet dies für den vorhandenen DT-Knoten
  noch nicht direkt an.
- `cmake/tools_disk.cmake`: konstantes Tools-FAT-Image und SCSI-Schreibschutz.

Keine dieser Anpassungen verändert das installierte SDK. Die Anwendung nutzt USB-next.

## Prüfungen

```sh
/opt/nordic/ncs/toolchains/322ac893fe/bin/python bootloader/verify.py
/opt/nordic/ncs/toolchains/322ac893fe/bin/python tests/verify_usb_audio.py build/multi_cdc_vscode_ready/zephyr/zephyr.elf
/opt/nordic/ncs/toolchains/322ac893fe/bin/python tests/verify_tools_disk.py build/multi_cdc_vscode_ready/generated/olf_tools.img build/multi_cdc_vscode_ready/zephyr/zephyr.elf
```

Zusätzlich vorhanden: Signaltests mit Sanitizern (`tests/tone_test.c`), native
Client-PTY-Tests und Tests des generierten SCSI-Codes mit simuliertem
schreibgeschütztem Medium. Die Bootloader-Prüfung kontrolliert Adressgrenzen,
Partitionen sowie DFU-Inhalt und Firmwarehash.

Der Build und die Dateiprüfungen ersetzen keinen Hardwaretest. USB-DFU und
paralleler Audio-/CDC-/MSC-Betrieb sind auf dem Dongle noch zu prüfen.
Es wurde keine Hardware programmiert.
