# PlanRadar API Analysis

## Ziel der Analyse

Vor der Implementierung wurde zuerst geprüft, wie der konkrete PlanRadar-Account die relevanten Wasserzähler-Ablesungen tatsächlich modelliert. Dabei wurden sowohl die offizielle PlanRadar-Dokumentation als Primärquelle als auch Live-Responses mit dem bereitgestellten API-Key verwendet.

## Offizielle Quellen

- Open API Overview: https://help.planradar.com/hc/en-gb/articles/15480453097373-Open-APIs
- API Tutorials for Ticket Endpoints: https://help.planradar.com/hc/en-gb/articles/33440893023133-API-Tutorials-for-Ticket-Endpoints
- Core API Concepts: https://help.planradar.com/hc/en-gb/articles/33438887517853-Core-API-Concepts

## Live bestätigte Endpunkte

### 1. Projekte laden

Bestätigt:

- `GET /api/v2/{customer_id}/projects/my_projects`
- `GET /api/v1/{customer_id}/projects`

Ergebnis für den bereitgestellten Account:

- `nggenml` -> `Beispielprojekt Facility-/ Objektmanager`
- `wddpbya` -> `Neugasse 7, 1452 Gaubendorf`

Entscheidung:

- Für die Projektauswahl wird primär `v2 my_projects` verwendet.
- `target_project_id` ist die stabilste Option.
- `target_project_name` wird zusätzlich unterstützt, wenn die ID noch nicht bekannt ist.

### 2. Tickets laden

Bestätigt:

- `GET /api/v2/{customer_id}/projects/{project_id}/tickets`
- `GET /api/v2/{customer_id}/projects/{project_id}/tickets/{uuid}`

Live beobachtete Struktur:

- `ticket-type-id` identifiziert das verwendete Formular
- benutzerdefinierte Feldwerte liegen in `typed-values`
- `typed-values` enthält technische Feld-IDs statt sprechender Namen

Beispiel:

```json
{
  "ticket-type-id": "egmmqkp",
  "typed-values": {
    "tf1f3ba4c76f5a9a9e": 6460,
    "tf29707c30571959ae": "2026-03-18",
    "tf37ce2025589dac7a": "Hauptzähler 1",
    "tf98c51e50d9efc265": "qkypaooq"
  }
}
```

### 3. Ticket Types / Formulare laden

Bestätigt:

- `GET /api/v2/{customer_id}/projects/{project_id}/ticket_types/ticket_type_project`
- `GET /api/v1/{customer_id}/ticket_types/{ticket_type_id}`

Für das Zielprojekt wurden drei zugewiesene Ticket Types gefunden. Relevant für den Use Case ist:

- Name: `Wasserzählerablesung neu`

Live bestätigte Felder:

- `Datum`
- `Zählerplatz & Zählernummer`
- `Zählerstand`
- `Anmerkungen`

Entscheidung:

- Die Implementierung erkennt das relevante Formular automatisch aus den echten Feldnamen.
- Optional kann per Config ein Ticket-Type-Override gesetzt werden.

### 4. Listenwerte für Zählerplatz / Zählernummer

Wichtige Beobachtung:

- Das Formularfeld `Zählerplatz & Zählernummer` ist ein `ListType`.
- Die `typed-values` enthalten **nicht** direkt die sichtbaren Namen, sondern Listen-Eintrags-IDs.
- Die zunächst geprüfte globale Liste `GET /api/v1/{customer_id}/lists/{list_id}` reichte hier **nicht** aus, weil die tatsächlichen Ticketwerte aus einer projektbezogenen hierarchischen Liste stammen.

Bestätigt:

- `GET /api/v1/{customer_id}/projects/{project_id}/lists`

Live beobachtete projektbezogene Liste:

- Listen-ID: `naeeaam`
- Name: `Zählerplätze  & Zählernummern`
- `is-hierarchy: true`

Struktur:

- Ebene 1 = Zählerplatz
  - `gwynjadl` -> `Sub_Z_1`
  - `kqewykjj` -> `Haupt_Z_2`
  - `podagymy` -> `Haupt_Z_1`
- Ebene 2 = Wasserzählernummer
  - `bqwlpeeb` -> `W 604823` (Kind von `Sub_Z_1`)
  - `donqzbbo` -> `W 85501` (Kind von `Haupt_Z_2`)
  - `qkypaooq` -> `W 10710295` (Kind von `Haupt_Z_1`)

Entscheidung:

- Für die fachliche Auflösung werden projektbezogene Listen geladen.
- Wenn ein Ticketwert auf einen Kindeintrag zeigt, dann:
  - Elterneintrag = `meter_location`
  - Kindeintrag = `meter_number`

Diese Auflösung ist für den gegebenen Account entscheidend und wurde direkt in die Pipeline übernommen.

### 5. Attachments

Bestätigt:

- `GET /api/v2/{customer_id}/projects/{project_id}/tickets/{ticket_uuid}/attachments`

Live beobachtete Struktur:

- Ticket-Attachment-Metadaten liegen in `data`
- die eigentlichen Bild-URLs liegen in `included`

Für den ersten Umsetzungsschritt werden Attachments nicht heruntergeladen, aber die Metadaten werden optional mitgeführt.

Für die implementierte Pipeline werden diese Attachments nun lokal gespeichert; in der Excel wird der relative Pfad zur heruntergeladenen Datei bzw. Dateiliste abgelegt.

## Minimal ausreichender Datenfluss

Aus der Live-Analyse wurde folgender minimaler Datenfluss abgeleitet:

1. `GET /api/v2/{customer_id}/projects/my_projects`
2. `GET /api/v2/{customer_id}/projects/{project_id}/ticket_types/ticket_type_project`
3. `GET /api/v1/{customer_id}/projects/{project_id}/lists`
4. `GET /api/v2/{customer_id}/projects/{project_id}/tickets`
5. optional `GET /api/v2/{customer_id}/projects/{project_id}/tickets/{ticket_uuid}/attachments`

`GET /api/v1/{customer_id}/ticket_types/{ticket_type_id}` bleibt als mögliche Fallback-Route relevant, ist für den aktuellen Flow aber nicht zwingend nötig.

## Filterstrategie

### Serverseitig

- Projekt wird serverseitig gewählt, indem direkt projektbezogene Endpunkte aufgerufen werden.
- Eine zusätzliche serverseitige Ticketfilterung war für diesen ersten Schritt nicht nötig, da das Zielprojekt nur wenige Tickets enthält.

### Clientseitig

- Relevante Tickets werden clientseitig über `ticket-type-id` eingeschränkt.
- Historische und neue Datensätze werden clientseitig auf den gewünschten `target_meter_location` reduziert.
- Stringvergleiche werden normalisiert.

## Rate-Limit-Folgerungen

Offiziell dokumentiert und praktisch übernommen:

- 30 Requests pro Minute pro Account

Daraus abgeleitet:

- Standardpause zwischen Requests: 2.1 Sekunden
- Retry/Backoff für `429` und temporäre `5xx`-Fehler
- keine unnötigen Detail-Endpunkte
- Listen- und Ticket-Type-Daten werden gesammelt geladen und wiederverwendet

## Abgeleitete Implementierungsentscheidung

Auf Basis der realen API wurde eine absichtlich schlanke Architektur gewählt:

- ein kleiner `PlanRadarClient` mit Rate-Limit-Schutz
- ein `discovery`-Modul für Projekt-, Formular-, Listen- und Ticket-Mapping
- ein einfaches Excel-Import-Modul
- ein Merge-Modul
- ein Excel-Output-Modul
- optionaler Download des Projekt-Titelbilds über `GET /api/v1/{customer_id}/projects/{project_id}` und das Attribut `project-image`

Kein generisches Plattform-Framework, weil die Live-Analyse gezeigt hat, dass der konkrete Use Case mit wenigen klaren Schritten sauber abbildbar ist.
