# Originaler Nordic Open Bootloader

Der aktive Build verwendet den bereits auf dem Dongle vorhandenen Bootloader.
Er baut und installiert keinen Ersatz-Bootloader. `build.py` ist ein Einstieg
zum Anwendungsbuild; MCUboot ist in `sysbuild.conf` deaktiviert.

| Bereich | Verwendung |
|---|---|
| `0x00000–0x00fff` | Vorhandener MBR, bleibt erhalten |
| `0x01000–0xdffff` | Anwendung |
| `0xe0000–0xfffff` | Vorhandener Bootloader und Settings, bleiben erhalten |

UICR ist nicht im HEX enthalten. `verify.py` prüft das fertige HEX, Partitionen
und den Inhalt des DFU-ZIPs und schreibt `build/openbootloader-verification.json`.

Bauen und Paket erzeugen:

```sh
python3 scripts/build_firmware.py --pristine
python3 scripts/package_openbootloader.py
/opt/nordic/ncs/toolchains/322ac893fe/bin/python bootloader/verify.py
```

Installation: RESET drücken (rote LED pulsiert), in nRF Connect for Desktop
Programmer den Dongle auswählen, das Anwendungs-HEX hinzufügen und Write
verwenden. Alternativ `nrfutil nrf5sdk-tools dfu usb-serial -pkg
build/multi_cdc_dfu.zip -p PORT` in einer Zeile ausführen.

Es ist kein SWD erforderlich, solange der originale Bootloader vorhanden ist.
Hier wurde noch kein Ersatz-Bootloader auf Hardware geflasht. Ein Gerät mit
bereits ersetzter Boot-Kette muss separat auf den originalen Bootloader
zurückgesetzt werden; dieses Anwendungspaket übernimmt das nicht.

Das DFU-Paket ist unsigniert. Der originale Open Bootloader erzwingt keine
Signaturprüfung. Archivierte Builds: `LEGACY_MCUBOOT.md`, `LEGACY_NRF5.md`
und `archive/`. Diese Konfigurationen gehören nicht zum aktiven Build.
