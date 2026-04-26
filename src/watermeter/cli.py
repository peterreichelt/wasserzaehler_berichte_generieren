from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .exceptions import WatermeterImportError
from .importing.pipeline import run_pipeline
from .logging_utils import configure_logging
from .reporting import run_reporting


def build_parser() -> argparse.ArgumentParser:
    """Baut den Kommandozeilenparser der Anwendung.

    Returns:
        argparse.ArgumentParser: Vollständig konfigurierter Parser für `run`
        und `report`.
    """
    parser = argparse.ArgumentParser(prog="watermeter")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Führt den Importlauf aus.")
    run_parser.add_argument("--config", required=True, help="Pfad zur YAML-Konfigurationsdatei.")

    report_parser = subparsers.add_parser("report", help="Erzeugt PDF-Reports aus einer kombinierten Arbeitsmappe.")
    report_parser.add_argument("--config", required=True, help="Pfad zur YAML-Konfigurationsdatei.")
    report_parser.add_argument(
        "--input-workbook",
        help="Optionaler Pfad zu einer combined_readings-Arbeitsmappe. Überschreibt reporting.input_workbook_path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Führt die CLI aus und übersetzt Fehler in Exit-Codes.

    Args:
        argv: Optionale Liste von Kommandozeilenargumenten.

    Returns:
        int: Prozess-Rückgabecode.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        configure_logging(config.log_level)
        if args.command == "run":
            output_path, summary = run_pipeline(config)
            logging.getLogger(__name__).info(
                "Fertig. Ausgabe wurde nach %s für Projekt %s und Ticket-Typ %s geschrieben.",
                output_path,
                summary.project_name,
                summary.ticket_type_name,
            )
        elif args.command == "report":
            report_paths = run_reporting(config, input_workbook_path=args.input_workbook)
            logging.getLogger(__name__).info("Fertig. %s Bericht(e) wurden erzeugt.", len(report_paths))
        return 0
    except WatermeterImportError as exc:
        parser.exit(status=2, message=f"Fehler: {exc}\n")
    except Exception as exc:  # pragma: no cover - defensive
        parser.exit(status=3, message=f"Unerwarteter Fehler: {exc}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
