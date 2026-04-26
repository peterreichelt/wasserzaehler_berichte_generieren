from pathlib import Path

import pytest

from watermeter.exceptions import ConfigError
from watermeter.integrations.planradar.client import PlanRadarClient


def test_from_env_files_requires_real_dotenv_file(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text("PLANRADAR_API_KEY=example-key\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        PlanRadarClient.from_env_files(
            customer_id="1531527",
            env_files=[str(tmp_path / ".env")],
            request_pause_seconds=2.1,
        )
