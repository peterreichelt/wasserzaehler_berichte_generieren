from __future__ import annotations

import re
import unicodedata
from pathlib import Path


SPACE_RE = re.compile(r"\s+")
FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def normalize_text(value: object) -> str:
    """Normalisiert beliebige Werte in einen bereinigten Text.

    Args:
        value: Zu normalisierender Eingabewert.

    Returns:
        str: Bereinigter Text ohne führende und doppelte Leerzeichen.
    """
    if value is None:
        return ""
    text = str(value).strip()
    text = SPACE_RE.sub(" ", text)
    return text


def normalize_key(value: object) -> str:
    """Erzeugt einen robusten Vergleichsschlüssel für Textwerte.

    Args:
        value: Zu normalisierender Eingabewert.

    Returns:
        str: Kleingeschriebener und akzentbereinigter Vergleichsschlüssel.
    """
    text = normalize_text(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


def normalize_meter_location(value: object) -> str:
    """Vereinheitlicht Zählerplatz-Bezeichnungen auf ein stabiles Format.

    Args:
        value: Rohwert des Zählerplatzes.

    Returns:
        str: Vereinheitlichte Kennung des Zählerplatzes.
    """
    text = normalize_key(value)
    number_match = re.search(r"(\d+)", text)
    number_suffix = f"_{number_match.group(1)}" if number_match else ""
    if "haupt" in text or text.startswith("hz"):
        return f"HAUPT_Z{number_suffix}"
    if "sub" in text or text.startswith("sz"):
        return f"SUB_Z{number_suffix or '_1'}"
    compact = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return compact.upper()


def property_signature(value: object) -> tuple[str, ...]:
    """Zerlegt eine Liegenschaftsangabe in vergleichbare Tokens.

    Args:
        value: Rohwert der Liegenschaft.

    Returns:
        tuple[str, ...]: Sortierte Tokens der Liegenschaft.
    """
    text = normalize_key(value)
    return tuple(sorted(TOKEN_RE.findall(text)))


def sanitize_filename(value: str) -> str:
    """Bereinigt einen Wert für die Verwendung als Dateiname.

    Args:
        value: Ursprünglicher Dateiname oder Dateinamensbestandteil.

    Returns:
        str: Sicherer Dateiname ohne problematische Sonderzeichen.
    """
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    safe = FILENAME_RE.sub("_", ascii_only.strip())
    safe = safe.strip("._")
    return safe or "output"


def sanitize_filename_preserve_extension(value: str) -> str:
    """Bereinigt einen Dateinamen und behält die Endung bei.

    Args:
        value: Ursprünglicher Dateiname.

    Returns:
        str: Bereinigter Dateiname inklusive Erweiterung.
    """
    path = Path(normalize_text(value) or "attachment")
    suffix = path.suffix
    stem = path.stem if suffix else path.name
    safe_stem = sanitize_filename(stem)
    safe_suffix = sanitize_filename(suffix.lstrip(".")) if suffix else ""
    return f"{safe_stem}.{safe_suffix}" if safe_suffix else safe_stem


def excel_column_to_index(column: str) -> int:
    """Wandelt eine Excel-Spaltenbezeichnung in einen nullbasierten Index um.

    Args:
        column: Excel-Spalte wie `A` oder `AB`.

    Returns:
        int: Nullbasierter Spaltenindex.
    """
    value = normalize_text(column).upper()
    result = 0
    for char in value:
        if not ("A" <= char <= "Z"):
            raise ValueError(f"Ungültige Excel-Spalte: {column}")
        result = result * 26 + (ord(char) - 64)
    return result - 1


def ensure_directory(path: Path) -> None:
    """Stellt sicher, dass ein Verzeichnis existiert.

    Args:
        path: Zu erzeugender oder zu prüfender Verzeichnispfad.
    """
    path.mkdir(parents=True, exist_ok=True)
