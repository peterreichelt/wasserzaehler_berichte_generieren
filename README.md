# watermeter

`watermeter` verbindet historische Wasserzähler-Ablesungen aus einer Excel-Datei mit neuen Ablesungen aus PlanRadar, baut daraus eine gemeinsame Datenbasis und erzeugt daraus professionelle Reports.

Das Tool ist bewusst schlank gehalten:

- Es liest bestehende Excel-Daten ein.
- Es lädt passende Tickets aus PlanRadar.
- Es führt beide Datenquellen in einer gemeinsamen Tabelle zusammen.
- Es lädt auf Wunsch die Ticket-Fotos aus PlanRadar herunter und speichert deren relative Pfade in der Ergebnis-Excel.
- Es kann aus einer vorhandenen `combined_readings.xlsx` professionelle PDF-Reports pro Liegenschaft und Zählerplatz erzeugen.

## Was macht das Tool?

Das Tool ist für zwei typische Arbeitsweisen gedacht:

- **Fokussierter Modus**: Sie möchten genau **eine Liegenschaft** und genau **einen Zählerplatz** verarbeiten.
- **Sammelmodus**: Sie möchten **eine große Gesamtdatei** über alle Liegenschaften und Zählerplätze erzeugen.

Die Betriebsart wird nicht über zusätzliche CLI-Parameter gesteuert, sondern nur über die YAML-Config.

## Voraussetzungen

Sie brauchen:

- Python 3.9 oder neuer
- Zugriff auf die gewünschte PlanRadar-Instanz
- einen gültigen PlanRadar API Key
- eine historische Excel-Datei mit den vorhandenen Ablesedaten

## Installation

Alle Befehle in dieser README müssen **im Projektordner `wasserzaehler`** ausgeführt werden.

Beispiel:

macOS / Linux:

```bash
cd /Pfad/zum/wasserzaehler
```

Windows PowerShell:

```powershell
cd C:\Pfad\zum\wasserzaehler
```

Erst danach die weiteren Befehle ausführen.

Im Projektordner ausführen:

macOS / Linux:

```bash
pip install -e '.[dev]'
```

Windows PowerShell:

```powershell
pip install -e ".[dev]"
```

Für den PDF-Report-Renderer wird zusätzlich ein lokales Chromium benötigt:

macOS / Linux:

```bash
python -m playwright install chromium
```

Windows PowerShell:

```powershell
python -m playwright install chromium
```

## Erste Einrichtung

### 1. `.env` anlegen

Im Projektordner muss eine Datei `.env` liegen. Diese Datei wird **beim Lauf zwingend benötigt**.

Nutzen Sie dafür die Vorlage aus `.env.example` und tragen Sie Ihren echten Schlüssel in `.env` ein:

```env
PLANRADAR_API_KEY=replace-with-your-real-planradar-api-key
```

Wichtig:

- `.env.example` ist **nur eine Vorlage**
- `.env.example` wird **nicht** beim Lauf verwendet
- ohne gültige `.env` bricht das Tool mit einer Fehlermeldung ab

### 2. Config-Datei anlegen

Kopieren Sie die Beispiel-Datei `config/config.example.yaml` nach `config/config.yaml` und passen Sie die Werte an.

## Betriebsarten

### Fokussierter Modus

Diesen Modus verwenden Sie, wenn Sie nur eine einzelne Liegenschaft und einen einzelnen Zählerplatz verarbeiten möchten.

Dann muss in der Config Folgendes gesetzt sein:

- `target_meter_location`
- genau **eines** von:
  - `target_project_id`
  - `target_project_name`

Beispiel:

```yaml
input_excel_path: input/wasserzaehler_auswertung_mit_zählerplätzen_anonymisiert.xlsx
output_dir: output
customer_id: 1531527
target_project_id: wddpbya
target_project_name:
target_meter_location: Haupt_Z_1
log_level: INFO
```

### Sammelmodus

Diesen Modus verwenden Sie, wenn Sie eine große Gesamtdatei für alle Liegenschaften und Zählerplätze erzeugen möchten.

Dann müssen diese drei Felder leer bleiben:

- `target_project_id`
- `target_project_name`
- `target_meter_location`

Beispiel:

```yaml
input_excel_path: input/wasserzaehler_auswertung_mit_zählerplätzen_anonymisiert.xlsx
output_dir: output
customer_id: 1531527
target_project_id:
target_project_name:
target_meter_location:
log_level: INFO
```

Im Sammelmodus gilt:

- zuerst werden alle Liegenschaften und Zählerplätze aus der Excel-Datei berücksichtigt
- danach werden zusätzlich weitere PlanRadar-Projekte aufgenommen, auch wenn es dafür keinen Excel-Match gibt
- das Ergebnis wird in **eine** große Excel-Datei geschrieben

## Wichtige Config-Felder

- `input_excel_path`: Pfad zur historischen Excel-Datei
- `output_dir`: Zielordner für Excel-Datei und Fotos
- `customer_id`: PlanRadar Customer ID
- `target_project_id`: optionale stabile Projekt-ID für den fokussierten Modus
- `target_project_name`: optionaler Projektname für den fokussierten Modus
- `target_meter_location`: fachlicher Zählerplatz für den fokussierten Modus
- `log_level`: z. B. `INFO`

### Excel-Mapping

Standardmäßig erwartet das Tool diese Spalten:

- `A`: Wasserzählernummer
- `B`: Ablesedatum
- `C`: Zählerstand
- `I`: Liegenschaft
- `N`: Zählerplatz

Falls Ihre Datei anders aufgebaut ist, können Sie das unter `excel.columns` anpassen.

## Schnellstart für Nicht-Entwickler

Wenn Sie das Tool nur zuverlässig starten müssen, gehen Sie genau in dieser Reihenfolge vor:

1. Terminal öffnen
2. In den Projektordner wechseln:

macOS / Linux:

```bash
cd /Pfad/zum/wasserzaehler
```

Windows PowerShell:

```powershell
cd C:\Pfad\zum\wasserzaehler
```

3. Prüfen, dass diese Dateien vorhanden sind:
   - `.env`
   - `config/config.yaml`
   - die historische Excel-Datei aus `input_excel_path`
4. Falls das Projekt auf diesem Rechner noch nicht eingerichtet wurde, einmalig installieren:

macOS / Linux:

```bash
pip install -e '.[dev]'
python -m playwright install chromium
```

Windows PowerShell:

```powershell
pip install -e ".[dev]"
python -m playwright install chromium
```

5. Danach genau einen der folgenden Läufe starten:
   - Excel-Datenbasis erzeugen: `python -m watermeter.cli run --config config/config.yaml`
   - Reports aus vorhandener Gesamtdatei erzeugen: `python -m watermeter.cli report --config config/config.yaml`

Wichtig:

- Die Befehle immer **im Projektordner** starten
- Nicht aus `src/`, `config/` oder `output/` starten
- Wenn ein Fehler erscheint, zuerst prüfen, ob `.env` und `config/config.yaml` vorhanden sind

## Starten des Tools

### Importlauf

MacOS:

```bash
python -m watermeter.cli run --config config/config.yaml
```

Windows PowerShell:

```powershell
python -m watermeter.cli run --config config/config.yaml
```

### Reporting-Lauf

MacOS:

```bash
python -m watermeter.cli report --config config/config.yaml
```

Windows PowerShell:

```powershell
python -m watermeter.cli report --config config/config.yaml
```

Optional kann eine bestehende kombinierte Excel-Datei direkt übergeben werden:

MacOS:

```bash
python -m watermeter.cli report --config config/config.yaml --input-workbook output/all_properties__combined_readings.xlsx
```

Windows PowerShell:

```powershell
python -m watermeter.cli report --config config/config.yaml --input-workbook output/all_properties__combined_readings.xlsx
```

## Was wird erzeugt?

### Ergebnis-Excel

Im Zielordner `output_dir` wird eine neue Excel-Datei erzeugt.

- im fokussierten Modus: eine kleinere Datei für genau eine Liegenschaft und einen Zählerplatz
- im Sammelmodus: `all_properties__combined_readings.xlsx`

Die Tabelle `combined_readings` enthält unter anderem:

- Herkunft des Datensatzes
- Liegenschaft
- Zählerplatz
- Wasserzählernummer
- Ablesedatum
- Zählerstand
- PlanRadar-Projekt-ID
- Ticket-ID
- Anzahl der Attachments
- relative Attachment-Pfade

### PDF-Reports

Der Reporting-Schritt liest die kombinierte Excel-Datei und erzeugt pro Kombination aus Liegenschaft und Zählerplatz genau einen PDF-Report.

Die PDFs werden standardmäßig hier abgelegt:

`output/reports/<property>/<strasse>__<plz_ort>__Zaehlerplatz__<meter_location>.pdf`

Die Reports enthalten:

- Deckblatt mit Titelbild der Liegenschaft
- Tabellen- und Diagrammseiten für die Ablesedaten
- Fotoseiten mit PlanRadar-Attachments

Der Reporting-Renderer nutzt intern `HTML/CSS + Playwright/Chromium`, damit Tabellen und Diagramme konsistent und druckstabil erzeugt werden.

### Titelbilder

Titelbilder werden standardmäßig unter `assets/cover-images` gesucht.

Beim Import werden vorhandene PlanRadar-Projekt-Titelbilder automatisch aus dem Projekt-Detail-Endpunkt geladen und in genau dieser Struktur abgelegt.

Unterstützte Konventionen:

- `assets/cover-images/<sanitized-property>/cover.jpg`
- `assets/cover-images/<sanitized-property>/cover.jpeg`
- `assets/cover-images/<sanitized-property>/cover.png`
- `assets/cover-images/<sanitized-property>/cover.webp`
- `assets/cover-images/<sanitized-property>.jpg`
- `assets/cover-images/<sanitized-property>.jpeg`
- `assets/cover-images/<sanitized-property>.png`
- `assets/cover-images/<sanitized-property>.webp`

Bevorzugt schreibt der Import nach:

- `assets/cover-images/<sanitized-property>/cover.<ext>`

Wichtig:

- vorhandene lokale Cover-Dateien für diese Liegenschaft werden beim Import überschrieben
- wenn PlanRadar kein `project-image` liefert, bleibt die vorhandene Reporting-Fallback-Logik aktiv

Wenn kein Titelbild gefunden wird, verwendet der Report automatisch einen generischen Platzhalter.

### Attachments / Fotos

Wenn Attachments aktiviert sind, werden die Fotos lokal gespeichert.

Die Ablage sieht so aus:

`attachments/<project_id>/<meter_location>/<ticket_id>/<ticket_id>_<photo_running_number>.<ext>`

Beispiel:

`attachments/wddpbya/HAUPT_Z_1/olqdpkgp/olqdpkgp_1.JPG`

In der Excel-Datei steht dazu pro Datensatz die Spalte `attachment_paths`. Mehrere Dateien werden mit `; ` getrennt.

## Typischer Ablauf

1. `.env` mit API-Key anlegen
2. `config/config.yaml` anpassen
3. Terminal öffnen
4. in den Projektordner wechseln
5. Tool per CLI starten
6. PlanRadar-Daten werden geladen
7. Excel- und PlanRadar-Daten werden zusammengeführt
8. Ergebnis-Excel und Attachments werden im Output-Ordner abgelegt

## Häufige Fehler

### `No valid PlanRadar API key found`

Ursache:

- keine `.env` vorhanden
- `PLANRADAR_API_KEY` fehlt in `.env`

Lösung:

- prüfen, dass die Datei wirklich `.env` heißt
- prüfen, dass sie im Projektordner `wasserzaehler` liegt
- den Befehl erneut **im Projektordner** starten

### `config/config.yaml` wird nicht gefunden

Ursache:

- der Befehl wurde aus dem falschen Ordner gestartet
- oder die Datei wurde noch nicht aus `config/config.example.yaml` kopiert

Lösung:

- zuerst in den Projektordner wechseln
- dann prüfen, ob `config/config.yaml` vorhanden ist

### Reporting startet, aber Chromium fehlt

Ursache:

- Playwright/Chromium wurde auf dem Rechner noch nicht installiert

Lösung:

```bash
cd /Pfad/zum/wasserzaehler
python -m playwright install chromium
```
- der Wert ist leer

Lösung:

- `.env` anlegen
- `PLANRADAR_API_KEY` korrekt eintragen

### Konfigurationsfehler zu Projekt / Zählerplatz

Ursache:

- die Config enthält eine Mischform aus fokussiertem Modus und Sammelmodus

Lösung:

- entweder genau ein Projekt plus einen Zählerplatz angeben
- oder alle drei Selektoren leer lassen

### Kein Match zwischen Excel und PlanRadar

Ursache:

- der Liegenschaftsname in Excel passt nicht zum Projektnamen in PlanRadar
- der Zählerplatz ist unterschiedlich geschrieben

Lösung:

- Schreibweisen prüfen
- falls nötig Mapping oder Datenbasis anpassen

## API-Analyse und Feldmapping

Die Struktur des Tools wurde aus der realen PlanRadar-API abgeleitet. Die wichtigsten Erkenntnisse stehen in `docs/API_ANALYSIS.md`.

Wichtige Punkte:

- Authentifizierung über `X-PlanRadar-API-Key`
- Projekte über `GET /api/v2/{customer_id}/projects/my_projects`
- Tickets über `GET /api/v2/{customer_id}/projects/{project_id}/tickets`
- Ticket Types über `GET /api/v2/{customer_id}/projects/{project_id}/ticket_types/ticket_type_project`
- Listen über `GET /api/v1/{customer_id}/projects/{project_id}/lists`
- Attachments über `GET /api/v2/{customer_id}/projects/{project_id}/tickets/{ticket_uuid}/attachments`

Das Feldmapping wird zuerst automatisch aus den echten Ticket-Type-Feldern abgeleitet. Falls ein Projekt Sonderfälle hat, können kleine Overrides in der Config gesetzt werden.

## Tests

Die Tests laufen ohne Live-API:

```bash
pytest
```

Sie verwenden kleine JSON-Fixtures aus `tests/fixtures/planradar`.
