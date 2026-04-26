# Markiert die Basisklasse für alle fachlichen Fehler der Anwendung.
class WatermeterImportError(Exception):
    """Basisklasse für die Anwendungsfehler."""


# Signalisiert ungültige oder unvollständige Konfiguration.
class ConfigError(WatermeterImportError):
    """Fehler in der Konfiguration."""


# Signalisiert Probleme mit der historischen Excel-Datei.
class ExcelDataError(WatermeterImportError):
    """Fehler in den Excel-Eingabedaten."""


# Signalisiert Probleme beim Zugriff auf die PlanRadar-API.
class PlanRadarApiError(WatermeterImportError):
    """Fehler bei der Verarbeitung der PlanRadar-API."""


# Signalisiert Probleme beim Erzeugen oder Rendern der Reports.
class ReportingError(WatermeterImportError):
    """Fehler im Reporting-Schritt."""
