"""CSV-backed implementation of DataRepository.

Loads each CSV from data/processed/ exactly as-is (same column names, same
values) and serves it as plain dicts. No column is renamed, no value is
recomputed — this layer is a pass-through, not an analysis step.

CSVs are read once per process and cached in memory (they are small, static
analysis outputs, not something the service mutates), which keeps repeated
API calls cheap without needing a database yet.
"""
import math
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import CsvFiles, DATA_PROCESSED_DIR
from app.data_access.repository import DataRepository, Record


def _clean_value(value: Any) -> Any:
    """Convert pandas/numpy NaN to None so it serializes as JSON null."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _records(df: pd.DataFrame) -> list[Record]:
    return [
        {col: _clean_value(val) for col, val in row.items()}
        for row in df.to_dict(orient="records")
    ]


class CsvDataRepository(DataRepository):
    def __init__(self, data_dir: Path = DATA_PROCESSED_DIR):
        self._data_dir = data_dir
        self._cache: dict[str, pd.DataFrame] = {}

    def _load(self, filename: str) -> pd.DataFrame:
        if filename not in self._cache:
            path = self._data_dir / filename
            if not path.exists():
                raise FileNotFoundError(f"Required CSV not found: {path}")
            # utf-8-sig strips the BOM present in these CSVs so the first
            # column name comes back as "country", not "﻿country".
            self._cache[filename] = pd.read_csv(path, encoding="utf-8-sig")
        return self._cache[filename]

    @staticmethod
    def _find_by_country(records: list[Record], country: str) -> Record | None:
        for record in records:
            if record.get("country") == country:
                return record
        return None

    # -- country_profile_base.csv ---------------------------------------
    def list_countries(self) -> list[str]:
        df = self._load(CsvFiles.COUNTRY_PROFILE_BASE)
        return df["country"].tolist()

    def get_country_profiles(self) -> list[Record]:
        return _records(self._load(CsvFiles.COUNTRY_PROFILE_BASE))

    def get_country_profile(self, country: str) -> Record | None:
        return self._find_by_country(self.get_country_profiles(), country)

    # -- gap_analysis.csv -------------------------------------------------
    def get_gap_analysis(self) -> list[Record]:
        return _records(self._load(CsvFiles.GAP_ANALYSIS))

    def get_gap_analysis_for_country(self, country: str) -> Record | None:
        return self._find_by_country(self.get_gap_analysis(), country)

    # -- conditional_gap_analysis.csv -------------------------------------
    def get_conditional_gap_analysis(self) -> list[Record]:
        return _records(self._load(CsvFiles.CONDITIONAL_GAP_ANALYSIS))

    def get_conditional_gap_analysis_for_country(self, country: str) -> Record | None:
        return self._find_by_country(self.get_conditional_gap_analysis(), country)

    # -- barrier_pattern_analysis.csv --------------------------------------
    def get_barrier_pattern_analysis(self) -> list[Record]:
        return _records(self._load(CsvFiles.BARRIER_PATTERN_ANALYSIS))

    def get_barrier_pattern_for_country(self, country: str) -> Record | None:
        return self._find_by_country(self.get_barrier_pattern_analysis(), country)

    # -- country_bottleneck_profile.csv ------------------------------------
    def get_bottleneck_profiles(self) -> list[Record]:
        return _records(self._load(CsvFiles.COUNTRY_BOTTLENECK_PROFILE))

    def get_bottleneck_profile_for_country(self, country: str) -> Record | None:
        return self._find_by_country(self.get_bottleneck_profiles(), country)

    # -- bottleneck_type_summary.csv ---------------------------------------
    def get_bottleneck_type_summary(self) -> list[Record]:
        return _records(self._load(CsvFiles.BOTTLENECK_TYPE_SUMMARY))

    # -- gap_barrier_correlation.csv ----------------------------------------
    def get_gap_barrier_correlation(self) -> list[Record]:
        return _records(self._load(CsvFiles.GAP_BARRIER_CORRELATION))

    # -- sensitivity_analysis.csv --------------------------------------------
    def get_sensitivity_analysis(self) -> list[Record]:
        return _records(self._load(CsvFiles.SENSITIVITY_ANALYSIS))

    # -- country_indicator_distribution.csv -----------------------------------
    def get_country_indicator_distribution(self) -> list[Record]:
        return _records(self._load(CsvFiles.COUNTRY_INDICATOR_DISTRIBUTION))

    # -- country_pattern_profile.csv -------------------------------------------
    def get_country_pattern_profiles(self) -> list[Record]:
        return _records(self._load(CsvFiles.COUNTRY_PATTERN_PROFILE))

    def get_country_pattern_profile_for_country(self, country: str) -> Record | None:
        return self._find_by_country(self.get_country_pattern_profiles(), country)
