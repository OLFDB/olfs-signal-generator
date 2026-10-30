> Archivierter Nordic-nRF5-Signierweg. Aktueller Stand: MCUboot, siehe README.md.

# Firmware-Signierung

Das aktuelle Paket `build/multi_cdc_dfu_signed.zip` wurde mit einem neu
angelegten ECDSA-P256-Schlüssel signiert (SHA-256). Das bisherige unsignierte
Paket bleibt unverändert. Die Firmware einschließlich Tools-Laufwerk ist
inhaltlich identisch; die Signatur liegt im Nordic-DFU-Init-Paket und bindet
den SHA-256-Hash der Firmware ein.

## Schlüssel

- `private/dfu_signing.pem`: privater Signierschlüssel, Dateirechte 0600,
  Verzeichnis 0700, über `.gitignore` ausgeschlossen. Separat sicher sichern;
  nicht in Firmware, USB-Laufwerk, DFU-Paket oder App-Download aufnehmen.
- `dfu_public.pem` und `dfu_public.der`: öffentlicher Prüfschlüssel.
- `dfu_public_key.c`: öffentlicher Schlüssel im Nordic-Secure-DFU-C-Format.
- `public-key.sha256`: SHA-256-Fingerprint des öffentlichen DER-Schlüssels.

Fingerprint:
`104a6354cda3b321fc6601343011c8c7355680e2dabc4f88f54f7333ae79acb4`

## Neues Paket signieren

Nach dem Firmware-Build, aus dem Projektordner:

```sh
nrfutil nrf5sdk-tools pkg generate --hw-version 52 --sd-req 0x00 --application build/multi_cdc_vscode_ready/zephyr/zephyr.hex --application-version 1 --app-boot-validation VALIDATE_ECDSA_P256_SHA256 --key-file signing/private/dfu_signing.pem build/multi_cdc_dfu_signed.zip
```

Die Anwendungs-Version ist derzeit 1; bei späterem Secure-DFU-Betrieb die
Versionsrichtlinie des Bootloaders berücksichtigen und Release-Versionen
entsprechend erhöhen. Kein neuer Schlüssel pro Build: denselben Schlüssel
für nachfolgende Releases verwenden.

## Unabhängige Prüfung

Die Prüfung benötigt nur den öffentlichen Schlüssel und das `ecdsa`-Paket,
das in der lokalen Nordic-Toolchain-Python-Umgebung vorhanden ist:

```sh
/opt/nordic/ncs/toolchains/322ac893fe/bin/python scripts/verify_signed_dfu.py build/multi_cdc_dfu_signed.zip signing/dfu_public.pem --require-boot-signature --report build/multi_cdc_dfu_signed.verification.json
```

Geprüft werden die ECDSA-Signatur der Init-Daten, der darin gebundene SHA-256-
Hash und die Länge des Firmware-Binaries sowie die zusätzliche ECDSA-Signatur
für die Anwendungsprüfung bei jedem Boot. Tests mit manipuliertem Binary
und manipulierter Signatur werden abgewiesen. Das signierte Binary ist mit
dem vorhandenen unsignierten Paket identisch.

## Bootloader

Das Signieren des Pakets ändert den vorhandenen offenen Nordic-Bootloader
nicht. Eine verbindliche Prüfung auf dem Dongle erfordert einen Secure-DFU-
Bootloader mit diesem öffentlichen Schlüssel und aktivierter Signaturpflicht.
Die Annahme eines signierten Pakets durch den originalen Bootloader wurde
nicht auf Hardware getestet. Der passende Bootloader wurde inzwischen gebaut; siehe `../bootloader/README.md`.
Er wurde nicht installiert, und das Paket wurde nicht geflasht. Diese Signatur ist keine Authenticode- oder
Developer-ID-Signierung der Desktopprogramme und kein MCUboot-Imageformat.
