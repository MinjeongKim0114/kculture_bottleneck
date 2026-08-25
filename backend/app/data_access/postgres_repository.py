"""PostgreSQL(Supabase)-backed implementation of DataRepository.

Mirrors csv_repository.py: no column is renamed, no value is recomputed.
Tables are created by backend/db/schema.sql, loaded from the same CSVs in
data/processed/ that csv_repository.py reads directly.
"""
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.core.config import DATABASE_URL
from app.data_access.repository import DataRepository, Record


class PostgresDataRepository(DataRepository):
    def __init__(self, database_url: str | None = None):
        self._database_url = database_url or DATABASE_URL
        if not self._database_url:
            raise RuntimeError("DATABASE_URL is not set (check backend/.env)")

    def _query(self, sql: str, params: tuple = ()) -> list[Record]:
        with psycopg.connect(self._database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def _query_one(self, sql: str, params: tuple = ()) -> Record | None:
        rows = self._query(sql, params)
        return rows[0] if rows else None

    # -- country_profile_base ---------------------------------------
    def list_countries(self) -> list[str]:
        rows = self._query("SELECT country FROM country_profile_base ORDER BY country")
        return [row["country"] for row in rows]

    def get_country_profiles(self) -> list[Record]:
        return self._query("SELECT * FROM country_profile_base ORDER BY country")

    def get_country_profile(self, country: str) -> Record | None:
        return self._query_one(
            "SELECT * FROM country_profile_base WHERE country = %s", (country,)
        )

    # -- gap_analysis -------------------------------------------------
    def get_gap_analysis(self) -> list[Record]:
        return self._query("SELECT * FROM gap_analysis ORDER BY country")

    def get_gap_analysis_for_country(self, country: str) -> Record | None:
        return self._query_one(
            "SELECT * FROM gap_analysis WHERE country = %s", (country,)
        )

    # -- conditional_gap_analysis -------------------------------------
    def get_conditional_gap_analysis(self) -> list[Record]:
        return self._query("SELECT * FROM conditional_gap_analysis ORDER BY country")

    def get_conditional_gap_analysis_for_country(self, country: str) -> Record | None:
        return self._query_one(
            "SELECT * FROM conditional_gap_analysis WHERE country = %s", (country,)
        )

    # -- barrier_pattern_analysis --------------------------------------
    def get_barrier_pattern_analysis(self) -> list[Record]:
        return self._query("SELECT * FROM barrier_pattern_analysis ORDER BY country")

    def get_barrier_pattern_for_country(self, country: str) -> Record | None:
        return self._query_one(
            "SELECT * FROM barrier_pattern_analysis WHERE country = %s", (country,)
        )

    # -- country_bottleneck_profile ------------------------------------
    def get_bottleneck_profiles(self) -> list[Record]:
        return self._query("SELECT * FROM country_bottleneck_profile ORDER BY country")

    def get_bottleneck_profile_for_country(self, country: str) -> Record | None:
        return self._query_one(
            "SELECT * FROM country_bottleneck_profile WHERE country = %s", (country,)
        )

    # -- bottleneck_type_summary ---------------------------------------
    def get_bottleneck_type_summary(self) -> list[Record]:
        return self._query("SELECT * FROM bottleneck_type_summary ORDER BY type_code")

    # -- gap_barrier_correlation ----------------------------------------
    def get_gap_barrier_correlation(self) -> list[Record]:
        return self._query("SELECT * FROM gap_barrier_correlation")

    # -- sensitivity_analysis --------------------------------------------
    def get_sensitivity_analysis(self) -> list[Record]:
        return self._query("SELECT * FROM sensitivity_analysis")

    # -- country_indicator_distribution -----------------------------------
    def get_country_indicator_distribution(self) -> list[Record]:
        return self._query("SELECT * FROM country_indicator_distribution")

    # -- country_pattern_profile -------------------------------------------
    def get_country_pattern_profiles(self) -> list[Record]:
        return self._query("SELECT * FROM country_pattern_profile ORDER BY country")

    def get_country_pattern_profile_for_country(self, country: str) -> Record | None:
        return self._query_one(
            "SELECT * FROM country_pattern_profile WHERE country = %s", (country,)
        )
