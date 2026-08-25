"""Assembles per-screen payloads for dashboard_information_architecture.md.

This layer only joins (by `country`), filters, or sorts records that the
data-access layer already returns as-is. It never recomputes a statistic
that isn't already a column in one of the CSVs listed in
dashboard_data_dictionary.md.
"""
from app.core.config import BARRIER_COLUMNS, BARRIER_GROUPS
from app.data_access.repository import DataRepository, Record
from app.services.exceptions import CountryNotFoundError, InvalidComparisonRequestError


def _top_barriers(barrier_record: Record, top_n: int = 3) -> list[dict]:
    """Sort the 8 existing barrier % columns and take the top N.

    Pure selection/sort of already-computed values — not a new statistic.
    """
    pairs = [
        {"barrier": col, "rate_pct": barrier_record[col]}
        for col in BARRIER_COLUMNS
        if barrier_record.get(col) is not None
    ]
    pairs.sort(key=lambda p: p["rate_pct"], reverse=True)
    return pairs[:top_n]


class DashboardService:
    def __init__(self, repo: DataRepository):
        self._repo = repo

    # -- Overview -----------------------------------------------------------
    def get_overview(self) -> dict:
        return {
            "indicator_distribution": self._repo.get_country_indicator_distribution(),
            "country_grid": self._build_country_grid(),
            "bottleneck_type_summary": self._repo.get_bottleneck_type_summary(),
            "country_bottleneck_profiles": self._repo.get_bottleneck_profiles(),
            "direct_gap": self._repo.get_gap_analysis(),
            "conditional_gap": self._repo.get_conditional_gap_analysis(),
        }

    def _build_country_grid(self) -> list[dict]:
        gap_by_country = {
            record["country"]: record for record in self._repo.get_gap_analysis()
        }
        grid = []
        for profile in self._repo.get_country_profiles():
            gap_record = gap_by_country.get(profile["country"])
            grid.append(
                {
                    "country": profile["country"],
                    "culture_experience_rate_pct": profile["culture_experience_rate_pct"],
                    "visit_intention_positive_pct": profile["visit_intention_positive_pct"],
                    "observed_gap_pct_point": gap_record["observed_gap_pct_point"]
                    if gap_record
                    else None,
                    "top_visit_barrier": profile["top_visit_barrier"],
                    "top_visit_barrier_rate_pct": profile["top_visit_barrier_rate_pct"],
                }
            )
        return grid

    # -- Country Explorer -----------------------------------------------------
    def get_country_detail(self, country: str) -> dict:
        profile = self._repo.get_country_profile(country)
        if profile is None:
            raise CountryNotFoundError(country)

        barrier_record = self._repo.get_barrier_pattern_for_country(country)

        return {
            "profile": profile,
            "pattern_profile": self._repo.get_country_pattern_profile_for_country(country),
            "direct_gap": self._repo.get_gap_analysis_for_country(country),
            "conditional_gap": self._repo.get_conditional_gap_analysis_for_country(country),
            "barrier_pattern": barrier_record,
            "top_barriers": _top_barriers(barrier_record) if barrier_record else [],
            "bottleneck_profile": self._repo.get_bottleneck_profile_for_country(country),
        }

    # -- Gap Explorer -----------------------------------------------------------
    def get_gap_explorer(self) -> dict:
        direct_conditional_correlation = [
            record
            for record in self._repo.get_gap_barrier_correlation()
            if "Conditional_Gap" in record["pair"]
        ]
        return {
            "direct_gap": self._repo.get_gap_analysis(),
            "conditional_gap": self._repo.get_conditional_gap_analysis(),
            "direct_vs_conditional_correlation": direct_conditional_correlation,
        }

    # -- Barrier Explorer -----------------------------------------------------
    def get_barrier_explorer(self) -> dict:
        return {
            "barrier_pattern": self._repo.get_barrier_pattern_analysis(),
            "barrier_groups": BARRIER_GROUPS,
        }

    # -- Comparison -----------------------------------------------------------
    def get_comparison(self, countries: list[str]) -> dict:
        if not 2 <= len(countries) <= 3:
            raise InvalidComparisonRequestError(
                "Comparison requires selecting 2 to 3 countries."
            )
        return {
            "countries": [self.get_country_detail(country) for country in countries]
        }
