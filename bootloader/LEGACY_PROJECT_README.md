# OLFs Signal Generator – nRF52840 Dongle

## Öffnen in VS Code (nRF Connect for VS Code)

1. ZIP **in einen Ordner entpacken**.
2. In VS Code **Datei → Ordner öffnen** und **genau diesen Ordner** auswählen; `CMakeLists.txt`, `prj.conf` und `app.overlay` müssen direkt darin liegen.
3. In der Seitenleiste **nRF Connect** öffnen.
4. Unter **Applications** (bzw. im Welcome-/Applications-Bereich) auf **Add Application** / **Add Existing Application** klicken und denselben Ordner wählen. Ein bloßes Öffnen eines Ordners registriert nicht bei allen Versionen automatisch eine Anwendung.
5. Über **Add Build Configuration** Toolchain/SDK wählen und Board `nrf52840dongle/nrf52840` einstellen. **Pristine Build** ausführen.

Anmerkung: Das Build-Log aus dem letzten Versuch zeigt Pfade zu NCS **3.2.1**. Bitte die gewünschte SDK-Version in der Build-Konfiguration ausdrücklich kontrollieren.

Terminal-Alternative (im Projektverzeichnis):

```sh
west build -p always -b nrf52840dongle/nrf52840 .
```

Die Firmware stellt USB Audio Class 2 (Dongle → Rechner), CDC 0 (Shell), CDC 1 (Logs) und ein schreibgeschütztes USB-Tools-Laufwerk bereit. Sie verwendet den USB-next-Stack mit `CONFIG_USB_DEVICE_STACK_NEXT=y` und `CONFIG_USB_DEVICE_STACK=n`.

## Installation mit originalem Nordic-Bootloader

Das Board ohne `/bare` verwenden. Die Anwendung startet bei `0x1000`; der vorhandene Nordic-Bootloader wird per USB-DFU beibehalten.

Das Overlay deaktiviert den zusätzlichen Board-CDC-Port, sodass genau zwei CDC-Instanzen aktiv sind.

Für den vorhandenen Sysbuild erzeugt dieser Befehl das DFU-Paket:

```sh
nrfutil nrf5sdk-tools pkg generate --hw-version 52 --sd-req 0x00 --application build/multi_cdc_vscode_ready/zephyr/zephyr.hex --application-version 1 build/multi_cdc_dfu.zip
```

RESET am Dongle drücken, bis die rote LED pulsiert. Anschließend das Paket übertragen (Port anpassen):

```sh
nrfutil nrf5sdk-tools dfu usb-serial -pkg build/multi_cdc_dfu.zip -p /dev/cu.usbmodemF5EA6A365B8F1
```

Bei einem Build ohne Sysbuild liegt die Anwendungsdatei unter `build/zephyr/zephyr.hex`.

## GPIO-Logs über die Shell

Das Anwendungsmodul `gpio_app` protokolliert das Schalten der grünen LED
(`led0`, P0.06, active-low). Debug-Meldungen sind einkompiliert.

```sh
log status
log enable dbg gpio_app
gpio_app led on
gpio_app led off
log enable inf gpio_app
log disable gpio_app
```

Die Logausgabe erfolgt ausschließlich über den zweiten CDC-Port. Die Shell steuert die Laufzeitfilter des Log-Backends; sie gelten bis zum Neustart.
Andere GPIO-Zugriffe werden durch dieses Modul nicht automatisch protokolliert.

## USB-Namen und Ports

Das Gerät heißt `OLFs Signal Generator`. Es hat zwei CDC-Schnittstellen:

- CDC 0: `OLF Shell` für Befehle und Befehlsantworten.
- CDC 1: `OLF Logs` für Logging und Konsole, ohne Shell.

Der zusätzliche Echo-Port entfällt. macOS vergibt die `/dev/cu.usbmodem*`-Pfade
selbst. Nach dem Flashen können sie sich ändern; normalerweise ist der erste
Port die Shell, der zweite der Logport. DTR im Terminal aktivieren.
Die Shell leitet keine asynchronen Logs mehr in ihre Anzeige um.

## USB-Audiogenerator

Der Rechner sieht das Gerät als Audio-Eingang (Aufnahmegerät). Die Firmware
sendet Stereo-PCM mit wählbaren 44,1, 48 oder 96 kHz und wählbaren 16 oder 24 Bit signed little-endian. In macOS
Audio-MIDI-Setup bzw. der Aufnahme-App `OLFs Signal Generator` auswählen.
Zum Anhören in der Audio-App Monitoring einschalten; ein Audio-Eingang wird
nicht automatisch über die Mac-Lautsprecher wiedergegeben.

Die Samples werden mit dem USB-SOF-Takt erzeugt: je nach Rate 44/45, 48 oder 96 Stereo-Frames pro Millisekunde. Die
Paketgröße folgt der gewählten Bittiefe (maximal 384 Byte bei 16 Bit bzw.
576 Byte bei 24 Bit),
kein zusätzlicher Feedback-Endpunkt und keine externe I2S-Hardware nötig.
Das Signal wird erst übertragen, wenn der Host den Audioeingang öffnet.

Nach dem Start des Dongles ist der Generator gestoppt (digitale Stille),
mit den Vorgaben Sinus, 1000 Hz, 25 % Spitzenamplitude und gekoppelten Kanälen.

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
- `gen freq 1..20000 [left|right|both]`: ganzzahlige Frequenz in Hz.
- `gen amp 0..100 [left|right|both]`: Spitzenamplitude in Prozent der digitalen Vollaussteuerung.
- `gen start [left|right|both]`: Signal aktivieren.
- `gen stop [left|right|both]`: Stille senden; der USB-Audiostream bleibt geöffnet.
- `gen link on`: rechts übernimmt Einstellungen, Start/Stopp und Phase von links;
  beide Ausgänge sind samplegenau identisch. Die bisherigen rechten Einstellungen
  werden überschrieben. Im Koppelmodus wirken Änderungen stets auf beide Kanäle,
  auch wenn `left` oder `right` angegeben wird.
- `gen link off`: Einstellungen bleiben erhalten; beide Kanäle lassen sich wieder
  getrennt ändern. Die Phasen laufen von ihrem aktuellen Stand weiter.
- Ohne Kanalangabe gelten Änderungen für beide Kanäle. Das setzt ihre Phasen im
  unabhängigen Modus nicht zurück; für identische Phasen `gen link on` verwenden.
- `gen status`: Einstellungen beider Kanäle, Kopplung, Host-Aufnahmestatus und Paket-/Fehlerzähler.

Die Einstellungen werden paketweise übernommen, die Oszillatorphase bleibt
über Paketgrenzen und Frequenzänderungen erhalten. Die Einstellungen liegen
im RAM. Rechteck und Dreieck sind direkt abgetastete Signalformen und nicht
bandbegrenzt; bei höheren Frequenzen treten Aliasanteile auf. Änderungen von
Signalform, Amplitude und Start/Stopp sind unmittelbar und können klicken.

Das Log-Modul `generator` protokolliert Einstellungen und Host-Streamwechsel
auf dem zweiten CDC-Port, ohne Meldungen pro Audiopaket. Zum Filtern:

```sh
log list_backends
log backend log_backend_uart enable inf generator
log backend log_backend_uart disable generator
```

## Prüfung

Firmware mit dem lokalen NCS 3.2.1 gebaut. Hosttests prüfen Signalform,
Sinusgenauigkeit, Frequenz, Amplitude, Stille , nahtlose Paketübergänge, Kanaltrennung, Kopplung und Stereo-Byte-Reihenfolge:

```sh
cc -std=c11 -Wall -Wextra -Werror -fsanitize=undefined,address -Isrc tests/tone_test.c src/tone.c -lm -o /tmp/olf-tone-test
/tmp/olf-tone-test
```

USB-Audio-Erkennung, Audioaufnahme, parallele CDC-Nutzung und wiederholtes
Öffnen/Schließen des Audiostreams sind noch auf Hardware zu prüfen.

## nRF52840: projektlokaler ISO-IN-Treiber und 96 kHz

Der Build ersetzt ausschließlich in dieser Anwendung die SDK-Datei
`drivers/usb/udc/udc_nrf.c` durch eine generierte Variante. Das installierte SDK
bleibt unverändert. `cmake/nrf52840_iso_in.cmake` führt dazu
`scripts/prepare_nrf_iso_in.py` aus und bindet die Ausgabe in die ursprüngliche
Zephyr-Treiberbibliothek ein. Bei nicht passenden Quelltextankern oder einer
anderen MCU bricht die Konfiguration ab. Getestete Grundlage: NCS 3.2.1.

Die vier Änderungen sind:

1. Beim Aktivieren des USB-Controllers `ISOSPLIT = OneDir` statt `HalfIN` setzen.
2. Den ISO-IN-Endpunkt mit maximal 1023 statt 511 Byte registrieren.
3. Den ISO-OUT-Endpunkt nicht registrieren.
4. Ein versehentliches Aktivieren von ISO OUT zusätzlich mit `-ENOTSUP` abweisen.

ISO IN bedeutet Dongle → Rechner. Diese Variante unterstützt kein Audio vom
Rechner zum Dongle. Die normalen Bulk-OUT-Endpunkte der CDC-Ports bleiben
verfügbar; Shell-Eingaben funktionieren weiter. Der vollständige ISO-Puffer
kann nicht zugleich für ISO IN und ISO OUT verwendet werden.

### Warum gibt es diese Grenze?

Der nRF52840 besitzt einen USB-2.0-Full-Speed-Controller mit 12 Mbit/s, keinen
High-Speed-Controller. USB-Full-Speed hat Frames von 1 ms. Ein isochroner
Endpunkt darf pro Frame höchstens ein Datenpaket mit 1023 Byte Nutzlast senden.
Der nRF52840 hat genau einen ISO-IN- und einen ISO-OUT-Endpunkt und einen
gemeinsamen internen ISO-Puffer mit 1 KiB. Im OneDir-Modus steht dieser einer
Richtung vollständig zur Verfügung. Diese Peripherie-Ressource ist vom RAM
für unsere Audio-Slabs unabhängig: größere Anwendungspuffer ändern die
USB-Paketgrenze nicht.

Das SDK stellt standardmäßig HalfIN ein und meldet je Richtung
`1023 / 2 = 511` Byte als maximale Paketgröße. Das ist die bisherige
Treiberbeschränkung. Unsere Anpassung nutzt den dokumentierten OneDir-Modus.

Stereo mit gepackten 24 Bit benötigt pro Audio-Frame 2 × 3 = 6 Byte.
Bei 96 kHz werden pro USB-Frame 96000 / 1000 = 96 Audio-Frames übertragen:

```
96 × 6 = 576 Byte pro Millisekunde
576 × 1000 × 8 = 4,608 Mbit/s reine Audionutzlast
```

| Abtastrate | Max. Audio-Frames je ms | USB-Nutzlast je ms | Mit OneDir passend? |
|---|---:|---:|---|
| 48 kHz | 48 | 288 Byte | Ja |
| 96 kHz | 96 | 576 Byte | Ja, jetzt konfiguriert |
| 144 kHz | 144 | 864 Byte | Rechnerisch ja, nicht getestet |
| 170 kHz | 170 | 1020 Byte | Rechnerische Obergrenze, nicht getestet |
| 176,4 kHz | 177 | 1062 Byte | Nein |
| 192 kHz | 192 | 1152 Byte | Nein |

Mit 1023 Byte passen höchstens floor(1023 / 6) = 170 vollständige Stereo-Frames
in ein Paket, also höchstens 170000 Audio-Frames/s. Bei nicht ganzzahligen
Samples/ms bestimmt das größte Paket die Grenze. 192 kHz überschreitet die
Paketgrenze, obwohl 9,216 Mbit/s reine Audionutzlast kleiner als 12 Mbit/s ist.
Die nominelle Busbitrate allein reicht für diese Beurteilung nicht: Tokens,
Paketköpfe, CRC, Bit-Stuffing und andere Transfers brauchen ebenfalls Buszeit.
USB-High-Speed-Mikroframes und mehrere ISO-IN-Endpunkte stehen hier nicht zur
Verfügung. Ein größeres USB-Gesamttransfer über mehrere Millisekunden würde
die nachhaltig übertragbare Abtastrate nicht erhöhen.

CDC verwendet andere Endpunkte/Puffer und kann parallel arbeiten, teilt sich
aber Buszeit, DMA und CPU mit Audio. Das tatsächliche Verhalten unter Last
muss deshalb auf Hardware geprüft werden. Die maximal einstellbare
Generatorfrequenz bleibt derzeit 20 kHz pro Kanal; die Abtastrate ist zwischen 44,1, 48 und 96 kHz wählbar.
Die Rechnung gilt gleichermaßen für nRF52840 Dongle und nRF52840 DK; das
vorliegende Overlay und DFU-Paket sind für den Dongle gebaut.

Quellen:
- [nRF52840 Product Specification v1.8, USBD und ISOSPLIT](https://docs-be.nordicsemi.com/bundle/nRF52840_PS_v1.8/raw/resource/enus/nRF52840_PS_v1.8.pdf)
- [USB-IF USB 2.0 Specification, Abschnitt 5.6.3](https://www.usb.org/document-library/usb-20-specification)

### Prüfung des 96-kHz-Builds

Die Host-Signaltests prüfen 48/96 kHz mit kompletten 48- bzw. 96-Sample-Paketen pro Kanal,
288-/576-Byte-Stereopaketen und Phasenkontinuität beim Ratenwechsel. Für
44,1 kHz werden zusätzlich die 44/45-Sample-Verteilung über eine volle Sekunde,
die korrekte Tonfrequenz und lückenlose Paketübergänge geprüft. Zusätzlich werden die tatsächlich einkompilierten
USB-Deskriptoren und die Frequenzentabelle aus `zephyr.elf` geprüft:

```sh
/opt/nordic/ncs/toolchains/322ac893fe/bin/python tests/verify_usb_audio.py build/multi_cdc_vscode_ready/zephyr/zephyr.elf
```

Erwartet werden eine Host-programmierbare Clock mit 44,1/48/96 kHz, zwei Kanäle
(links/rechts), drei Bytes pro Sample, 24 Bit und ein synchroner ISO-IN-Endpunkt
mit maximal 576 Byte pro 1-ms-Frame.
Build und Host-/ELF-Prüfungen sind bestanden. Noch offen ist der Hardwaretest:
Nach dem Flashen 96 kHz / 24 Bit / Stereo in der Audio-App prüfen, beide
Generatoren unterschiedlich einstellen, mindestens eine längere Aufnahme
machen und `gen status` vor/nach der Aufnahme auf Paketverluste prüfen.
Auch parallele Shell-/Lognutzung und wiederholtes Öffnen/Schließen testen.

## Abtastrate im Betrieb wählen

Der USB-Clock-Deskriptor bietet diskrete 44100, 48000 und 96000 Hz an. Der Host
wählt die Rate über die normalen USB-Audio-Class-2-Clock-Anfragen. Unter
macOS in Audio-MIDI-Setup das Gerät `OLFs Signal Generator` auswählen und
unter Format 44100, 48000 oder 96000 Hz mit 16 oder 24 Bit / zwei Kanälen einstellen.
Eine Aufnahme-App kann die Rate ebenfalls setzen; sie kann die zuvor in
Audio-MIDI-Setup gewählte Rate überschreiben.

`gen status` zeigt die tatsächlich aktive Rate und Bittiefe. Änderungen werden auf dem
Logport als `USB sample rate selected by host` gemeldet. Die interne Vorgabe
nach Neustart ist 96 kHz, bis der Host eine Rate auswählt. Bei 44,1 kHz enthält ein 10-ms-Zyklus neun Pakete mit je 44 und eines mit
45 Stereo-Frames. Ein Restakkumulator sorgt für exakt 44100 Frames pro Sekunde.
Beide Kanäle teilen
sich die Rate, können aber ihre Signalparameter unabhängig behalten.

Es gibt absichtlich keinen Shell-Befehl, der die Rate unabhängig vom Host
ändert: Sampleanzahl und Host-Takt müssen zusammenpassen. Frequenz, Amplitude,
Signalform und Kopplung bleiben über die Shell steuerbar. Beim Ratenwechsel
wird die Oszillatorphase beibehalten und der Phasenschritt neu berechnet.
Hardwareprüfung: Aufnahme bei allen drei Raten, mehrfacher Wechsel 44,1 → 48 → 96 → 44,1 kHz,
korrekte Tonfrequenzen und getrennte Kanäle sowie Paketverluste prüfen.

## 16 und 24 Bit zur Laufzeit auswählen

Das Gerät bietet im selben Stereo-Audiostream zwei aktive USB-Alternate-Settings
an: Alternate 1 mit 16 Bit (zwei Bytes pro Sample) und Alternate 2 mit 24 Bit
(drei Bytes pro Sample). Alternate 0 hat keine Bandbreite und beendet die
Aufnahme. Beide aktiven Formate unterstützen 44,1, 48 und 96 kHz. Der Host
wählt das Format in Audio-MIDI-Setup oder der Aufnahme-App; `gen status` zeigt
es an. Beide Kanäle teilen sich Bittiefe und Samplerate.

Die Generatoren arbeiten intern weiterhin mit 24-Bit-Samplewerten. Im
16-Bit-Modus werden die oberen 16 Bits als signed PCM little-endian übertragen,
ohne Dithering. Beim Formatwechsel werden weder Kanaleinstellungen noch
Oszillatorphasen zurückgesetzt. Der Host kann den Stream dafür stoppen und
neu öffnen. Solange noch kein aktives Format gewählt wurde, zeigt der Status
16 Bit an. Die Ratenvorgabe bleibt 96 kHz, bis der Host sie setzt.

| Abtastrate | 16 Bit Stereo, Byte je Paket | 24 Bit Stereo, Byte je Paket |
|---|---:|---:|
| 44,1 kHz | 176 oder 180 | 264 oder 270 |
| 48 kHz | 192 | 288 |
| 96 kHz | 384 | 576 |

Für die Formatauswahl ergänzt `cmake/uac2_formats.cmake` eine projektlokale
Variante der UAC2-Klasse. `scripts/prepare_uac2_formats.py` übernimmt den
SDK-Quelltext und die Makros in den Buildordner, ergänzt mit
`src/uac2_formats.h` das zweite Format und meldet das gewählte Alternate Setting
an die Anwendung. Beide Alternates verwenden denselben ISO-IN-Endpunkt.
Das SDK wird nicht verändert. Die Erweiterung ist ausdrücklich auf unseren
einzelnen synchronen Full-Speed-IN-Audiostream ausgelegt.

Die ELF-Prüfung liest die vollständige Descriptor-Pointerliste und prüft die
Alternates 0/1/2, beide PCM-Formate, gemeinsame Interface-/Endpunktadressen,
Paketgrößen, Clock-Tabelle und den internen Endpunktindex der UAC2-Klasse.
Hosttests prüfen zusätzlich die 16-Bit-Konvertierung einschließlich negativer
Werte und Stereo-Reihenfolge. Noch auf Hardware zu prüfen: alle sechs
Rate-/Bittiefenkombinationen, Wechsel zwischen ihnen und parallele CDC-Nutzung.

## Native Konsolenapps und USB-Laufwerk

Die Firmware enthält ein schreibgeschütztes FAT12-Laufwerk mit 512 KiB.
Es liegt als konstantes Image im internen Flash, benötigt keinen separaten
Datenträger und keine Flash-Schreibzugriffe zur Laufzeit. Die Dateien werden
mit dem normalen Anwendungs-DFU aktualisiert. Volume-Label: `OLFS TOOLS`.

Das Laufwerk enthält eigenständige Konsolenprogramme ohne Python-/Java-/NET-
Voraussetzung:

| Datei | System |
|---|---|
| `OLF-WIN.EXE` | Windows 10/11 x64 |
| `OLF-LX64` | Linux x86_64, statisch gelinkt |
| `OLF-LARM` | Linux ARM64, statisch gelinkt |
| `OLF-MAC` | macOS 11+, Intel und Apple Silicon (Universal Binary) |

Hinzu kommen `README.TXT`, `OLFCTL.C`, `SHA256.TXT`, `LICENSE.TXT` und
`BUILD.TXT`. Die Software startet nicht automatisch. Das passende Programm
zuerst vom USB-Laufwerk auf den Rechner kopieren. Auf macOS/Linux bei Bedarf
mit `chmod +x` ausführbar machen. Die ausführliche plattformspezifische
Anleitung steht in `host/DRIVE_README.txt` und auf dem Laufwerk.

Beispiel unter macOS:

```sh
chmod +x OLF-MAC
./OLF-MAC --list
./OLF-MAC --port /dev/cu.usbmodemXXXX status
./OLF-MAC --port /dev/cu.usbmodemXXXX
```

Im interaktiven Modus funktionieren etwa `link off`, `freq 1000 left`,
`wave triangle right`, `amp 25`, `start` und `stop`. Der Client ergänzt bei
Generatorbefehlen automatisch `gen`. Andere Shell-Befehle wie `gpio_app led on`
werden unverändert übertragen. `quit` oder Strg+C beendet das Programm.
Mit weiteren Argumenten nach dem Port wird ein einzelner Befehl ausgeführt.
`--list` listet Kandidaten, öffnet aber keine fremden Geräte automatisch.
Den tatsächlichen Shell-Port wählen, andere Terminalprogramme vorher trennen.
Samplerate und Bittiefe bleiben Einstellungen des USB-Audio-Hosts.

Die Windows-Datei hat keine Authenticode-Signatur; die Mac-Datei ist ad-hoc
signiert (für Apple Silicon), ohne Developer ID/Notarisierung. Es werden keine
Zugangsdaten oder Signaturschlüssel benötigt. Ausführungsrechte und lokale
Betriebssystemrichtlinien gelten weiterhin.

### Flash und USB-Ressourcen

Das Image wird per `.incbin` eingebunden; die 512 KiB werden nicht in den RAM
kopiert. Der Build belegt derzeit ca. 617 KiB Flash und ca. 33 KiB RAM. Eine
Linkerprüfung vergleicht die tatsächlich zu ladenden Flash-Daten mit Adresse
`0xe0000`, dem Beginn des originalen Nordic-Bootloaders. Die MPU-Ausrichtung
von `__rom_region_end` ist größer und ist nicht die geschriebene Firmwaregröße.
Die ELF-Prüfung kontrolliert zusätzlich alle Flash-Ladesegmente und die
vollständigen Image-/Dateiinhalte gegen die Originalprogramme.

MSC benötigt einen zusätzlichen Bulk-IN- und Bulk-OUT-Endpunkt. Mit beiden
CDC-Ports sind insgesamt fünf normale IN- und drei normale OUT-Endpunkte
belegt, zusätzlich zum Control-Endpunkt und dem separaten ISO-IN-Endpunkt.
Das passt in den nRF52840. Dateikopien teilen sich Buszeit, DMA und CPU mit
Audio; Programme vor längeren Audioaufnahmen kopieren.

Der lokale NCS-MSC-SCSI-Code benötigt eine kleine projektlokale Anpassung:
`DISK_STATUS_WR_PROTECT` darf lesbare Medien nicht als fehlend behandeln,
MODE SENSE(6/10) muss den Schreibschutz melden und WRITE(10) mit DATA PROTECT /
WRITE PROTECTED ablehnen. `scripts/prepare_msc_readonly.py` erzeugt diese
Variante im Buildordner. Das SDK bleibt unverändert. Der Disk-Treiber lehnt
jeden Schreibzugriff zusätzlich mit `-EROFS` ab.

### Konsolenapps neu bauen

Die fertigen Programme liegen unter `host/dist/`. Firmware-Builds benötigen
keinen Desktop-Cross-Compiler. Nach Änderungen an `host/olfctl.c` müssen die
nativen Programme zuerst neu gebaut werden; Quelltext- und Binärhashes werden
vor dem Erzeugen des Laufwerks geprüft, damit keine veralteten Clients
versehentlich ausgeliefert werden.

Der aktuelle Release-Build läuft auf macOS mit Xcode-Command-Line-Werkzeugen,
Python 3 (nur als Buildwerkzeug) und dem offiziellen Zig-0.14.1-Compiler.
Zig wurde von `https://ziglang.org/download/0.14.1/zig-x86_64-macos-0.14.1.tar.xz`
bezogen und gegen SHA-256
`b0f8bdfb9035783db58dd6c19d7dea89892acc3814421853e5752fe4573e5f43`
aus der offiziellen Downloadliste geprüft.

```sh
python3 host/build_clients.py --zig /pfad/zu/zig
cmake --build build
```

### Prüfung und verbleibende Hardwaretests

Bestanden: alle vier Binärformate gebaut/Architekturen geprüft, Mac-Signatur
geprüft, Mac-Client gegen einen Pseudo-Terminal-Shellsimulator getestet
(Einzelbefehle, interaktive Steuerung, Durchreichen, Fehlerfälle und Strg+C),
FAT-Dateisystem mit `fsck_msdos -n` geprüft, alle FAT-Dateien/Prüfsummen und ihre
Einbettung im ELF kontrolliert. Der tatsächlich generierte SCSI-Code wurde
auf dem Host gegen einen simulierten schreibgeschützten Datenträger getestet
(Ready, Kapazität, Lesen, beide MODE-SENSE-Varianten und Schreibabweisung).
USB-Audiodeskriptoren und bestehende Generatorfunktionen bleiben erhalten.

```sh
python3 tests/host_client_test.py host/dist/OLF-MAC
python3 tests/msc_readonly_test.py build/multi_cdc_vscode_ready/generated/usbd_msc_scsi_readonly.c /opt/nordic/ncs/v3.2.1/zephyr/subsys/usb/device_next/class
/opt/nordic/ncs/toolchains/322ac893fe/bin/python tests/verify_tools_disk.py build/multi_cdc_vscode_ready/generated/olf_tools.img build/multi_cdc_vscode_ready/zephyr/zephyr.elf
```

Noch offen: Laufwerk am echten Dongle auf allen drei OS mounten, Dateien
kopieren und Prüfsummen vergleichen; echte Windows-/Linux-Ausführung sowie
Mac-ARM64-Ausführung und parallele Audio-/CDC-/MSC-Nutzung auf Hardware testen.
Die Firmware wurde noch nicht auf den Dongle geflasht.

## Firmware-Signierung

Ein separat signiertes DFU-Paket liegt unter `build/multi_cdc_dfu_signed.zip`.
Details zu Schlüsselablage, Prüfung und Bootloader-Voraussetzungen stehen in
[signing/README.md](signing/README.md). Der private Schlüssel ist nicht Teil
des USB-Laufwerks oder eines Downloadpakets.

## Secure-DFU-Bootloader

Ein passender USB-Secure-DFU-Bootloader für den Dongle ist gebaut. Artefakte,
Speicheraufteilung, Sicherheitskonfiguration und noch offene Hardwaretests
stehen unter [bootloader/README.md](bootloader/README.md). Noch nicht installiert.
