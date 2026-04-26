from __future__ import annotations

import logging
from pathlib import Path

from ..config import AppConfig
from ..exceptions import PlanRadarApiError
from ..integrations.planradar.client import PlanRadarClient
from ..integrations.planradar.discovery import discover_and_load_readings, load_project_readings, load_projects
from ..shared.normalization import property_signature
from .attachments import download_attachments_for_readings, download_project_cover_image
from .excel import load_historical_readings
from .merge import collect_excel_meter_locations, combine_readings, filter_readings
from .models import DiscoverySummary
from .output import write_output_workbook


logger = logging.getLogger(__name__)


def _run_focused_pipeline(
    config: AppConfig,
    historical: list,
    client: PlanRadarClient,
) -> tuple[Path, DiscoverySummary]:
    """Führt den fokussierten Lauf für genau ein Projekt und einen Zählerplatz aus."""
    discovery = discover_and_load_readings(client, config)
    download_project_cover_image(
        client,
        config,
        project_id=discovery.summary.project_id,
        property_name=discovery.summary.project_name,
    )

    logger.info("Ablesungen werden für den Zählerplatz %s gefiltert", config.target_meter_location)
    planradar_filtered = filter_readings(
        discovery.readings,
        property_name=discovery.summary.project_name,
        meter_location=config.target_meter_location,
    )
    historical_filtered = filter_readings(
        historical,
        property_name=discovery.summary.project_name,
        meter_location=config.target_meter_location,
    )

    if not historical_filtered:
        logger.warning("Keine historischen Excel-Ablesungen passen zum gewählten Projekt und Zählerplatz.")
    if not planradar_filtered:
        logger.warning("Keine PlanRadar-Ablesungen passen zum gewählten Projekt und Zählerplatz.")

    if planradar_filtered:
        download_attachments_for_readings(client, planradar_filtered, config)

    combined = combine_readings(historical_filtered, planradar_filtered)
    logger.info("Kombinierte Arbeitsmappe mit %s Ablesungen wird geschrieben.", len(combined))
    output_path = write_output_workbook(
        config.output_dir,
        discovery.summary.project_name,
        config.target_meter_location or "ALL_METER_LOCATIONS",
        combined,
        discovery.summary,
    )
    return output_path, discovery.summary


def _run_bulk_pipeline(
    config: AppConfig,
    historical: list,
    client: PlanRadarClient,
) -> tuple[Path, DiscoverySummary]:
    """Führt den Sammelmodus über alle relevanten Liegenschaften und Zählerplätze aus."""
    logger.info("Sammelmodus über alle Excel-Liegenschaften und verbleibenden PlanRadar-Projekte wird ausgeführt.")
    excel_groups = collect_excel_meter_locations(historical)
    projects = load_projects(client, config.customer_id)
    project_map = {property_signature(project.get("attributes", {}).get("name")): project for project in projects}

    planradar_collections = []
    processed_project_ids: set[str] = set()

    for property_key, meter_locations in excel_groups.items():
        project = project_map.get(property_key)
        if not project:
            logger.warning("Kein PlanRadar-Projekt passt zur Excel-Liegenschaftssignatur '%s'.", property_key)
            continue
        try:
            discovery = load_project_readings(client, config, project, allowed_meter_locations=meter_locations)
        except PlanRadarApiError as exc:
            logger.warning("Projekt %s wird übersprungen, weil die Discovery fehlgeschlagen ist: %s", project["id"], exc)
            continue
        processed_project_ids.add(project["id"])
        if not discovery.readings:
            logger.warning("Keine PlanRadar-Ablesungen passen zu den Excel-Zählerplätzen für Projekt %s.", discovery.summary.project_name)
            continue
        download_project_cover_image(
            client,
            config,
            project_id=discovery.summary.project_id,
            property_name=discovery.summary.project_name,
        )
        planradar_collections.append(discovery.readings)

    for project in projects:
        if project["id"] in processed_project_ids:
            continue
        try:
            discovery = load_project_readings(client, config, project)
        except PlanRadarApiError as exc:
            logger.warning("Projekt %s wird übersprungen, weil die Discovery fehlgeschlagen ist: %s", project["id"], exc)
            continue
        if not discovery.readings:
            continue
        download_project_cover_image(
            client,
            config,
            project_id=discovery.summary.project_id,
            property_name=discovery.summary.project_name,
        )
        planradar_collections.append(discovery.readings)

    planradar_readings = combine_readings(*planradar_collections) if planradar_collections else []
    if planradar_readings:
        download_attachments_for_readings(client, planradar_readings, config)

    combined = combine_readings(historical, planradar_readings)
    logger.info("Sammel-Arbeitsmappe mit %s Ablesungen wird geschrieben.", len(combined))
    output_path = write_output_workbook(
        config.output_dir,
        "ALL_PROPERTIES",
        "ALL_METER_LOCATIONS",
        combined,
        None,
    )
    summary = DiscoverySummary(
        project_id="bulk",
        project_name="Alle Liegenschaften",
        ticket_type_id="multiple",
        ticket_type_name="mehrere",
        field_ids={},
        project_list_ids=[],
        notes=[],
    )
    return output_path, summary


def run_pipeline(config: AppConfig) -> tuple[Path, DiscoverySummary]:
    """Führt die vollständige Import-Pipeline von Excel bis Ausgabe aus."""
    logger.info("Historische Excel-Daten werden aus %s geladen", config.input_excel_path)
    historical = load_historical_readings(config.input_excel_path, config.excel)

    logger.info("Verbindung zu PlanRadar wird aufgebaut und die Discovery gestartet.")
    client = PlanRadarClient.from_env_files(
        customer_id=config.customer_id,
        env_files=[".env"],
        request_pause_seconds=config.planradar.request_pause_seconds,
    )
    if config.is_bulk_mode:
        return _run_bulk_pipeline(config, historical, client)
    return _run_focused_pipeline(config, historical, client)
