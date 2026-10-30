> Archivierter nRF5-SDK-Stand. Aktiver Bootloader ist jetzt MCUboot; siehe README.md.

# OLFs Secure USB DFU Bootloader – nRF52840 Dongle

Gebaut auf Basis des lokalen nRF5 SDK 17.1.0, USB-Secure-DFU-Beispiel für
PCA10056, angepasst auf PCA10059 (nRF52840 Dongle). Kein MCUboot, kein SoftDevice.
Das SDK wurde nicht verändert. Der originale Bootloader auf dem Dongle wurde
nicht überschrieben; Hardwaretests stehen aus.

## Artefakte unter `build/secure_bootloader/`

- `olfs_secure_bootloader.hex`: ausschließlich Bootloader-Code und zwei UICR-
  Adresswörter; kein Anwendungsimage und kein MBR.
- `olfs_secure_bootloader.out` / `.map`: ELF und Linker-Map für die Prüfung.
- `olfs_bootloader_settings.hex`: Einstellungen Version 2 einschließlich
  Backup und ECDSA-Bootsignatur für die aktuelle Anwendung Version 1.
- `olfs_secure_install_preserve_mbr.hex`: Bootloader + aktuelle Anwendung
  einschließlich Tools-Laufwerk + signierte Einstellungen/Backup, ohne MBR.
- `verification.json`: Prüfergebnis inklusive öffentlichem Schlüsselfingerprint.
- `build-info.json`: Board, Compiler, Schlüssel-Quelltexthash und Konfiguration.

Das zugehörige USB-Anwendungsupdate liegt unter `build/multi_cdc_dfu_signed.zip`.
Es wurde um `--app-boot-validation VALIDATE_ECDSA_P256_SHA256` ergänzt. Das
frühere Paket mit ausschließlich signiertem Init-Paket reicht für die jetzt
aktivierte Bootprüfung nicht. Das Anwendungsbinary selbst ist unverändert.

## Speicheraufteilung

| Bereich | Adresse |
|---|---|
| Bestehender Nordic MBR, unverändert | `0x00000` bis `0x00FFF` |
| Anwendung | ab `0x01000`, vor `0xE0000` |
| Neuer Secure-Bootloader | ab `0xE0000`, vor `0xFE000` |
| MBR-Parameter / Settings-Backup | `0xFE000` |
| Bootloader-Settings | `0xFF000` |
| UICR-Bootloaderadresse | `0x10001014` → `0xE0000` |
| UICR-MBR-Parameteradresse | `0x10001018` → `0xFE000` |

Der Bootloader belegt 35644 Byte im Flash. Die Anwendung belegt 631604 Byte.
Die Bereiche überlappen sich nicht. Das kombinierte HEX enthält keine Daten
unterhalb `0x1000` und setzt einen vorhandenen Nordic MBR voraus. Es ist kein
vollständiges Image für einen komplett gelöschten Chip. UICR-Spannungs- und
Reset-Pin-Einstellungen des vorhandenen Dongles werden nicht mit einem
pauschalen UICR-/Chip-Erase ersetzt.

## Sicherheits- und Bedienkonfiguration

- Updates benötigen ECDSA-P256/SHA-256 mit unserem vorhandenen Signierschlüssel.
- Jede Anwendung benötigt eine gültige ECDSA-Bootvalidierungssignatur und wird
  beim Start kryptographisch geprüft.
- Öffentlicher Schlüssel: `signing/dfu_public.pem`, auch als `dfu_public_key.c`.
- Fingerprint (DER SHA-256):
  `104a6354cda3b321fc6601343011c8c7355680e2dabc4f88f54f7333ae79acb4`.
- Privater Schlüssel wird weder in den Bootloader noch in die Pakete eingebaut.
- RESET führt in USB-DFU; alternativ SW1 an P1.06 beim Start gedrückt halten.
- USB-Produktname: `OLFs Secure DFU Bootloader`.
- Im DFU-Modus gibt es keinen Inaktivitäts-Timeout. Die SDK-LED-Anzeige ist
  statisch/ereignisgesteuert und entspricht nicht dem Pulsieren des Originals.
- Single-Bank-Updates sind aktiviert, da das aktuelle Anwendungsimage größer
  als eine halbe Flash-Bank ist. Bei unterbrochenem Update kann die Anwendung
  unvollständig sein; der Bootloader bleibt zur erneuten USB-Übertragung erhalten.
- Ältere Versionsnummern werden abgewiesen. Gleiche Versionsnummern sind für
  die derzeitige Entwicklung mit Version 1 erlaubt. Für Releases erhöhen.
- SWD bleibt offen zur Wiederherstellung; keine APPROTECT-/Debug-Sperre.
  Dies ist kein Schutz vor einem Angreifer mit physischem SWD-Zugriff.

## Installation

Die Erstinstallation ist für SWD/J-Link vorgesehen. Das kombinierte HEX ersetzt
Anwendung, Bootloader und Einstellungen, erhält aber den bestehenden MBR.
Nicht das Anwendungs-DFU-Kommando auf dieses Installations-HEX anwenden.
Die Installation wurde bewusst noch nicht ausgeführt. Vor dem tatsächlichen
Schreiben sind Ziel-Dongle, SWD-Verbindung und Sicherung des aktuellen Flash/
UICR konkret festzulegen. Ein gelöschter MBR müsste separat wiederhergestellt
werden; das vorbereitete Installationsimage enthält ihn nicht.

Nach installierter und getesteter Bootloader-Variante sind weitere Updates
über USB mit dem signierten Anwendungspaket möglich. Dafür RESET drücken und
mit `nrfutil nrf5sdk-tools dfu usb-serial -pkg build/multi_cdc_dfu_signed.zip -p PORT`
übertragen. Unsignierte Anwendungsupdates werden von dieser Variante abgewiesen.

## Reproduzierbarer Build

```sh
python3 bootloader/legacy_nrf5_build.py --sdk /Volumes/UserData/Downloads/nRF5_SDK_17.1.0_ddde560 --make /opt/local/bin/gmake --zstd-library /opt/local/lib/libzstd.1.dylib
```

Verwendet wurde Arm GNU GCC 14.2.1 unter `/usr/local/bin`. Dessen lokale
Installation erwartet libzstd an einem fehlenden Homebrew-Pfad. Der optionale
`--zstd-library`-Parameter stellt ausschließlich diese bereits vorhandene
Bibliothek über ein isoliertes Verzeichnis im Buildordner bereit; es werden
keine Systemdateien geändert. Auf einer intakten Compilerinstallation entfallen
`--zstd-library` und gegebenenfalls die abweichende `--make`-Angabe.

Für modernen GCC werden SDK-Linker-Section-Marker projektlokal als Arrays
unbekannter Länge statt als einzelne Pointerobjekte deklariert. Die binären
Linker-Sektionen bleiben unverändert. `--param=min-pagesize=0` erlaubt außerdem
korrekte Zugriffe auf gültige MBR-Flashadressen unterhalb 4 KiB. Sicherheits-
und Array-Bounds-Diagnosen werden nicht pauschal abgeschaltet.
GNU Make meldet einen Hinweis zur alten SDK-Assembler-Pattern-Regel; der
Linker meldet die unimplementierten Newlib-Datei-I/O-Stubs. Diese Stubs stellen
keinen USB-Transport bereit; DFU verwendet den SDK-USB-Treiber.

Die Settings lassen sich passend zur aktuellen Anwendung neu erzeugen:

```sh
nrfutil nrf5sdk-tools settings generate --family NRF52840 --application build/multi_cdc_vscode_ready/zephyr/zephyr.hex --application-version 1 --bootloader-version 1 --bl-settings-version 2 --app-boot-validation VALIDATE_ECDSA_P256_SHA256 --key-file signing/private/dfu_signing.pem build/secure_bootloader/olfs_bootloader_settings.hex
```

Nach jedem geänderten Anwendungsbuild Settings, signiertes Updatepaket und
kombiniertes Installationsimage erneut erzeugen:

```sh
/opt/nordic/ncs/toolchains/322ac893fe/bin/python bootloader/legacy_nrf5_merge_install.py
```

Beim Zusammenführen mit
IntelHex werden nur die abweichenden ELF-Entry-Point-Metadaten entfernt;
Datenüberlappungen bleiben Fehler. Der Reset erfolgt über den erhaltenen MBR.

## Verifikation

```sh
/opt/nordic/ncs/toolchains/322ac893fe/bin/python scripts/verify_signed_dfu.py build/multi_cdc_dfu_signed.zip signing/dfu_public.pem --require-boot-signature --report build/multi_cdc_dfu_signed.verification.json
/opt/nordic/ncs/toolchains/322ac893fe/bin/python bootloader/legacy_nrf5_verify.py
```

Geprüft: öffentlicher Schlüssel im tatsächlichen Bootloader-ELF, belegte
Crypto-/Flash-Instanzsektionen, Vektortabelle, UICR-Adressen, Flash-Grenzen,
Settings- und Bootvalidierungs-CRC, signierte Settings samt Backup, ECDSA-
Signaturen von Init-Daten und Anwendung, identisches Anwendungsbinary im
DFU-/Installationsimage sowie überlappungsfreie Zusammenführung ohne MBR.

Noch auf Hardware zu prüfen: erster Start über vorhandenen MBR, USB-Erkennung,
RESET/SW1-Einstieg, Start der gültig signierten Anwendung, Ablehnung von
unsignierten/manipulierten/falsch signierten Updates und Wiederaufnahme nach
abgebrochenem Single-Bank-Update. Es wurde noch nichts auf Hardware geschrieben.
