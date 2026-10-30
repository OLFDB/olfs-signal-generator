# Entwicklerdokumentation

[index.html](index.html) direkt im Browser öffnen. Die Seite funktioniert offline,
ohne Buildwerkzeug und ohne externe Fonts, Skripte oder Dienste.

Enthalten sind Architektur, Audio-Pipeline, USB-Paketbudget, Quelltextkarte,
Build und USB-DFU, Flash-Layout, native Clients und Testabläufe.
Die SVG-Grafiken unter `assets/` können separat verwendet werden.

Die Suche filtert Kapitel nach allen eingegebenen Begriffen. Über
**Drucken / PDF** lässt sich die vollständige Dokumentation exportieren;
die Druckansicht blendet Navigation aus und zeigt auch weggefilterte Kapitel.

Pflege: Inhalte in `index.html`, Gestaltung in `assets/docs.css`, Interaktionen
in `assets/docs.js`. SVGs sind textbasiert. Bei Änderungen an USB-Formaten,
Partitionen, Buildpfaden oder Hostplattformen die zugehörigen Abschnitte und
Grafiken aktualisieren. Verlinkte Projektdateien beziehen sich auf das
übergeordnete Projektverzeichnis.
