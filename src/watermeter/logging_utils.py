from __future__ import annotations

import logging


def configure_logging(level: str) -> None:
    """Konfiguriert das Standard-Logging der Anwendung.

    Args:
        level: Gewünschtes Log-Level als Text, z. B. `INFO`.
    """
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
