# MCUboot-Signierung

Der aktive NCS-Sysbuild signiert die Anwendung automatisch als MCUboot-Image
mit ECDSA-P256/SHA-256. Verwendet wird weiterhin der vorhandene Schlüssel,
nicht der MCUboot-Beispielschlüssel.

- Privat: `private/dfu_signing.pem`, Rechte 0600, Verzeichnis 0700, in `.gitignore`.
  Separat sicher sichern; nicht veröffentlichen oder in ein Image aufnehmen.
- Öffentlich: `dfu_public.pem` / `dfu_public.der`.
- SHA-256 des öffentlichen DER-Schlüssels:
  `104a6354cda3b321fc6601343011c8c7355680e2dabc4f88f54f7333ae79acb4`.
- Die C-Datei `dfu_public_key.c` ist der alte Nordic-Keyexport. MCUboot erzeugt
  seine eigene öffentliche C-Darstellung aus demselben Schlüssel im Buildordner.

```sh
python3 scripts/build_firmware.py
/opt/nordic/ncs/toolchains/322ac893fe/bin/python bootloader/verify.py
```

Aktuelles Update: `build/multi_cdc_vscode_ready/zephyr/zephyr.signed.bin`.
Die signierte Version stammt aus `VERSION`. Für normale Updates wird kein
neuer Schlüssel erzeugt. Beim Schlüsselwechsel muss auch der vertrauende
MCUboot-Bootloader entsprechend provisioniert werden.

Die bisherigen Nordic-DFU-ZIPs, `nrfutil --key-file`-Signierkommandos und
`verify_signed_dfu.py` gehören zum archivierten nRF5-SDK-Weg. Sie sind nicht
mit dem MCUboot-Imageformat austauschbar. Details dort: `LEGACY_NRF5.md`.
Die Firmware-Signatur ist keine Authenticode-/Developer-ID-Signatur der
Desktopprogramme.
