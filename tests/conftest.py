"""Shared fixtures: a temp project with CSV sources, scanned and profiled."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from ai_data_platform.sdk import ADPClient


@pytest.fixture()
def sample_data_dir(tmp_path: Path) -> Path:
    """Two related CSVs: customers (parent) and orders (child)."""
    rng = np.random.default_rng(7)
    n_cust, n_ord = 100, 500
    data = tmp_path / "data"
    data.mkdir()
    pl.DataFrame(
        {
            "customer_id": np.arange(1, n_cust + 1),
            "full_name": [f"Person {i}" for i in range(n_cust)],
            "email": [f"user{i}@example.com" for i in range(n_cust)],
            "city": rng.choice(["Pune", "Mumbai", "Delhi"], n_cust),
            "segment": rng.choice(["retail", "wholesale"], n_cust),
        }
    ).write_csv(data / "customers.csv")
    pl.DataFrame(
        {
            "order_id": np.arange(1, n_ord + 1),
            "customer_id": rng.integers(1, n_cust + 1, n_ord),
            "order_date": [
                f"2025-{m:02d}-{d:02d}"
                for m, d in zip(rng.integers(1, 13, n_ord), rng.integers(1, 28, n_ord))
            ],
            "total_amount": np.round(rng.lognormal(4.0, 0.5, n_ord), 2),
            "quantity": (rng.poisson(2, n_ord) + 1),
            "status": rng.choice(["completed", "pending", "cancelled"], n_ord),
        }
    ).write_csv(data / "orders.csv")
    return data


@pytest.fixture()
def project(tmp_path: Path, sample_data_dir: Path) -> ADPClient:
    """Initialized project with the CSV source connected (not yet scanned)."""
    from ai_data_platform.config import SourceConfig

    client = ADPClient(tmp_path)
    client.init("testproj")
    client.add_source(SourceConfig(name="shop", type="csv", path=str(sample_data_dir)), test=True)
    return client


@pytest.fixture()
def scanned_project(project: ADPClient) -> ADPClient:
    project.scan()
    return project


@pytest.fixture()
def profiled_project(scanned_project: ADPClient) -> ADPClient:
    scanned_project.profile()
    return scanned_project
