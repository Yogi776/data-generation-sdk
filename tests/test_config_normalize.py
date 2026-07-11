"""Tests for pipeline-style adp.yaml normalization."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_data_platform.config import load_config
from ai_data_platform.config_normalize import normalize_adp_yaml
from ai_data_platform.core.exceptions import ConfigError


def test_pipeline_format_to_destinations() -> None:
    raw = {
        "name": "wf-sf",
        "version": "v1",
        "type": "pipeline",
        "tags": ["snowflake"],
        "pipeline": {
            "source": {
                "address": "${SNOWFLAKE_SOURCE_URI}",
                "incremental_key": "updated_at",
            },
            "sink": {
                "address": "${SNOWFLAKE_DEST_URI}",
                "table_prefix": "PUBLIC",
                "incremental_strategy": "merge",
                "primary_key": "order_id",
            },
        },
    }
    norm = normalize_adp_yaml(raw)
    assert norm["project"] == "wf-sf"
    assert norm["version"] == 1
    assert len(norm["destinations"]) == 1
    dest = norm["destinations"][0]
    assert dest["name"] == "default"
    assert dest["uri"] == "${SNOWFLAKE_DEST_URI}"
    assert dest["source"]["uri"] == "${SNOWFLAKE_SOURCE_URI}"
    assert dest["incremental_strategy"] == "merge"
    assert norm["load"]["default_destination"] == "default"
    assert norm["load"]["require_quality_pass"] is False


def test_workflow_dag_stack_spec() -> None:
    raw = {
        "name": "wf-salesforce-account",
        "version": "v1",
        "workflow": {
            "dag": [
                {
                    "name": "sf-account",
                    "spec": {
                        "stack": "nilus:1.0",
                        "stackSpec": {
                            "source": {
                                "address": "salesforce://?username=${SF_USER}",
                                "options": {
                                    "source-table": "account",
                                    "primary-key": "id",
                                },
                            },
                            "sink": {
                                "address": "snowflake://${SNOWFLAKE_DEST_URI}",
                                "options": {
                                    "dest-table": "PUBLIC.account",
                                    "incremental-strategy": "merge",
                                },
                            },
                        },
                    },
                }
            ]
        },
    }
    norm = normalize_adp_yaml(raw)
    dest = norm["destinations"][0]
    assert dest["name"] == "sf-account"
    assert dest["source"]["uri"].startswith("salesforce://")
    assert dest["source"]["table"] == "account"
    assert dest["tables"] == {"account": "PUBLIC.account"}
    assert dest["incremental_strategy"] == "merge"


def test_legacy_destinations_passthrough() -> None:
    raw = {
        "project": "legacy",
        "version": 1,
        "destinations": [{"name": "d", "uri": "duckdb:///x.db"}],
    }
    norm = normalize_adp_yaml(raw)
    assert norm["destinations"][0]["name"] == "d"


def test_pipeline_load_from_file(tmp_path: Path) -> None:
    (tmp_path / "adp.yaml").write_text(
        """
name: demo
version: v1
pipeline:
  name: main
  sink:
    address: duckdb:///tmp/out.duckdb
    table_prefix: main
""",
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    assert cfg.project == "demo"
    assert cfg.destinations[0].name == "main"
    assert cfg.load.default_destination == "main"


def test_pipeline_missing_sink_raises() -> None:
    with pytest.raises(ValueError, match="sink"):
        normalize_adp_yaml({"name": "x", "pipeline": {"source": {"address": "pg://x"}}})


def test_invalid_pipeline_still_raises_on_validate(tmp_path: Path) -> None:
    (tmp_path / "adp.yaml").write_text("name: bad\npipeline: {}\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)
