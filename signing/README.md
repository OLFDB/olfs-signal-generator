# Signierung beim originalen Open Bootloader

Der aktive Build erzeugt ein unsigniertes Nordic-DFU-Anwendungspaket.
Der originale Nordic Open Bootloader erzwingt keine kryptografische
Signaturprüfung. Eine Paketsignatur allein würde diese Eigenschaft nicht ändern.

Der vorhandene private Schlüssel `private/dfu_signing.pem` bleibt für archivierte
oder zukünftige signierte Builds erhalten (Datei 0600, Verzeichnis 0700,
Git-Ausschluss). Er wird für den aktiven Build weder gelesen noch benötigt
und darf nicht in Installationspakete aufgenommen werden.

Die öffentlichen Dateien bleiben erhalten. Die bisherigen Anleitungen stehen
in `LEGACY_MCUBOOT.md` und `LEGACY_NRF5.md`; sie gelten nicht für den aktiven Build.
