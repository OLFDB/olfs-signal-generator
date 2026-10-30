# MCUboot – aktiver Bootloader

MCUboot wird jetzt gemeinsam mit der Anwendung durch NCS 3.2.1 Sysbuild gebaut.
Der separate nRF5-SDK-Bootloader ist nicht mehr der aktive Build. Dessen
Artefakte sind unter `artifacts/legacy-nrf5/` archiviert; die alte Beschreibung
steht in `LEGACY_NRF5.md`.

## Architektur und Speicher

Board: `nrf52840dongle/nrf52840/bare`.

| Bereich | Adresse / Größe |
|---|---|
| MCUboot | `0x00000..0x1FFFF` / 128 KiB reserviert |
| Primärer Slot mit Header | `0x20000..0xFFFFF` / 896 KiB |
| Image-Header | `0x20000..0x201FF` / 512 Byte |
| Anwendungs-Codebeginn | `0x20200` |
| Zweiter Slot | keiner |

`pm_static.yml` ist die verbindliche Aufteilung. MCUboot benötigt im geprüften
Build etwa 53 KiB Flash, das signierte Anwendungsimage einschließlich
512-KiB-Tools-Laufwerk etwa 619 KiB. Es passt in den einzelnen Slot.

MCUboot ist bewusst erster Bootloader ab 0x0. Ein vorgeschalteter offener
Nordic-Bootloader wäre ein unsignierter Austauschweg für MCUboot und könnte
dessen Schlüsselbindung umgehen. Die neue Erstinstallation ersetzt deshalb
den ursprünglichen MBR-Bootpfad und ist für SWD/J-Link vorgesehen. Das Image
ist kein Nordic-DFU-ZIP und darf nicht mit dem alten USB-DFU-Kommando behandelt
werden. Alte Nordic-Bootloader-/Settings-Seiten sind keine aktiven Partitionen
mehr. Das geprüfte Installations-HEX enthält keine UICR-Daten; bestehende
Spannungs-/Reset-Einstellungen dürfen bei der Provisionierung nicht unbedacht
verworfen werden.

## Sicherheit

- ECDSA-P256/SHA-256 mit dem vorhandenen privaten Schlüssel unter
  `signing/private/dfu_signing.pem`. Kein SDK-Beispielschlüssel.
- Öffentlicher DER-Fingerprint:
  `104a6354cda3b321fc6601343011c8c7355680e2dabc4f88f54f7333ae79acb4`.
- `CONFIG_BOOT_VALIDATE_SLOT0=y`: Prüfung bei jedem Start.
- `CONFIG_FPROTECT=y`: Schutz des Bootloader-Flashs im laufenden System.
- SWD wird nicht gesperrt. Physischer SWD-Zugriff ist weiterhin ein
  Wiederherstellungs- und Austauschweg; keine Anti-Tamper-Zusage.
- Signierte Versionsnummer derzeit 1.0.0+0 aus `VERSION`; es ist kein
  hardwarebasierter Rollbackzähler eingerichtet.

Single-Slot-Recovery überschreibt die einzige Anwendung. Bei Abbruch oder
ungültiger Signatur gibt es keine alte Anwendung als Rückfallversion. MCUboot
bleibt erhalten und soll den erneuten USB-Upload ermöglichen. Das ist auf
Hardware insbesondere nach Stromunterbrechung zu prüfen.

## Build und Signierung

```sh
python3 scripts/build_firmware.py --pristine
```

Alternativ `python3 bootloader/build.py --pristine`. Das ruft denselben
NCS-Sysbuild auf. `sysbuild.conf` setzt Single-Slot und ECDSA; der Schlüsselpfad
wird projektbezogen aufgelöst. `sysbuild/mcuboot.conf` setzt Recovery und
Bootprüfung. Die Anwendung und MCUboot werden aus demselben SDK gebaut.

Artefakte:

- `build/merged.hex`: MCUboot + signierte Anwendung zur Erstinstallation.
- `build/mcuboot/zephyr/zephyr.hex`: nur MCUboot.
- `build/multi_cdc_vscode_ready/zephyr/zephyr.signed.bin`: Recovery-Update.
- `build/multi_cdc_vscode_ready/zephyr/zephyr.signed.hex`: signierte Anwendung.
- `build/mcuboot-verification.json`: Prüfergebnis.
- `build/olfs-mcuboot-bundle.zip`: Paket mit Anleitung und SHA-256-Prüfsummen.

Der NCS-Signer erzeugt BIN und HEX getrennt. Die ECDSA-Signaturen können sich
aufgrund der Signatur-Nonces unterscheiden. Beide werden unabhängig geprüft;
der authentisierte Inhalt muss identisch sein. Das ist kein Firmware-Unterschied.

`build/dfu_application.zip` ist eine NCS-Verpackung des MCUboot-Images, kein
Nordic-nRF5-DFU-Paket. Für die hier dokumentierte serielle Recovery wird direkt
`zephyr.signed.bin` verwendet.

## Erstinstallation mit SWD/J-Link

Ohne Programmer ist diese Variante nicht über den bisherigen USB-Bootloader
installierbar. Geeignet sind ein SEGGER J-Link oder ein Nordic DK mit
Debug-Ausgang. Die konkrete Pinbelegung hängt vom Programmer/DK ab. SWDIO,
SWDCLK und gemeinsame Masse verbinden; die Spannungsreferenz muss zur VDD
am Dongle passen. Bei Versorgung des Dongles über USB wird dessen VDD OUT
als Zielspannungsreferenz verwendet, nicht die 5-V-VBUS-Leitung.

Nach Anschluss im Projektordner (SERiennummer des richtigen Programmers
statt `PROBE_ID` einsetzen; bei einem DK den externen Dongle als Ziel wählen):

```sh
nrfjprog --ids
nrfjprog --family NRF52 --snr PROBE_ID --readcode dongle-before-mcuboot.hex
nrfjprog --family NRF52 --snr PROBE_ID --readuicr dongle-uicr-before-mcuboot.hex
nrfjprog --family NRF52 --snr PROBE_ID --program build/merged.hex --sectorerase --verify
nrfjprog --family NRF52 --snr PROBE_ID --reset
```

`--sectorerase` löscht die betroffenen Flash-Seiten, erhält aber UICR. Kein
pauschales `--chiperase` oder `--recover` verwenden: diese würden auch die
bestehenden UICR-Einstellungen löschen. Der Programmiervorgang ersetzt den
MBR und den aktiven Bootpfad. Das Installationsimage enthält bereits die
signierte Anwendung; ein erster USB-Upload ist danach nicht zwingend nötig.
Die Backups werden durch diese Dokumentation nicht automatisch angelegt.

Quellen für die spätere konkrete Verkabelung und Programmierung:
- [Nordic Dongle SWD interface](https://docs.nordicsemi.com/r/bundle/ug_nrf52840_dongle/page/ug/nrf52840_dongle/hw_swd_if.html)
- [Nordic nrfjprog-Kommandoreferenz](https://docs.nordicsemi.com/r/bundle/ug_nrf_cltools/page/ug/cltools/nrf_nrfjprogexe_reference.html)

## USB Serial Recovery

Nach MCUboot-Installation startet RESET direkt die Recovery; alternativ SW1
beim Einschalten gedrückt halten. Ohne gültige Anwendung wird automatisch die
Recovery angeboten. Im normalen Betrieb ohne Recovery-Auslöser startet die
geprüfte Anwendung. Recovery meldet sich als `OLFs MCUboot Recovery` (Entwicklungs-VID/PID
`1209:0002`), separat
von den Shell-/Logports der Anwendung.

Mit separat installierter `mcumgr`-CLI:

```sh
mcumgr --conntype serial --connstring 'dev=PORT,baud=115200' image upload build/multi_cdc_vscode_ready/zephyr/zephyr.signed.bin
mcumgr --conntype serial --connstring 'dev=PORT,baud=115200' reset
```

`PORT` durch den konkreten Recovery-Port ersetzen. Bei einem Single-Slot-
Image gibt es keinen Test-Swap und keine zweite Version zum Bestätigen.
Die vorhandenen nativen Konsolenprogramme bleiben für die Steuerung der
laufenden Generator-Anwendung zuständig, nicht für SMP-Firmwareuploads.

## Verifikation und Status

```sh
/opt/nordic/ncs/toolchains/322ac893fe/bin/python bootloader/verify.py
```

Geprüft werden MCUboot-Header/Version, Slotgröße und Aufteilung, Boot-/Recovery-
und Flashschutz-Konfiguration, öffentlicher Schlüssel im Bootloader-ELF,
Signaturen beider Anwendungsformate durch das tatsächlich verwendete imgtool,
Abweisung eines manipulierten Binaries und eines falschen Prüfschlüssels sowie
Vektortabelle und Zusammenführung im Installations-HEX.

Build und diese Prüfungen sind bestanden. Noch nicht auf Hardware installiert
oder getestet. Die Erstinstallation muss den konkret angeschlossenen Dongle,
die SWD-Verbindung und dessen vorhandene UICR-Einstellungen berücksichtigen.
