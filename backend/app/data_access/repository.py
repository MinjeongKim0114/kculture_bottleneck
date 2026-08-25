"""Abstract data-access interface.

Every method returns plain dicts/lists whose keys are exactly the column
names defined in `dashboard_data_dictionary.md` — no renaming, no derived
statistics. This interface is the seam meant to make a future move to
PostgreSQL painless: only `csv_repository.py` needs a `PostgresDataRepository`
sibling that implements the same methods; the service/API layers stay
untouched.
"""
from abc import ABC, abstractmethod
from typing import Any


Record = dict[str, Any]


class DataRepository(ABC):
    # -- country_profile_base.csv ---------------------------------------
    @abstractmethod
    def list_countries(self) -> list[str]:
        ...

    @abstractmethod
    def get_country_profiles(self) -> list[Record]:
        ...

    @abstractmethod
    def get_country_profile(self, country: str) -> Record | None:
        ...

    # -- gap_analysis.csv -------------------------------------------------
    @abstractmethod
    def get_gap_analysis(self) -> list[Record]:
        ...

    @abstractmethod
    def get_gap_analysis_for_country(self, country: str) -> Record | None:
        ...

    # -- conditional_gap_analysis.csv -------------------------------------
    @abstractmethod
    def get_conditional_gap_analysis(self) -> list[Record]:
        ...

    @abstractmethod
    def get_conditional_gap_analysis_for_country(self, country: str) -> Record | None:
        ...

    # -- barrier_pattern_analysis.csv --------------------------------------
    @abstractmethod
    def get_barrier_pattern_analysis(self) -> list[Record]:
        ...

    @abstractmethod
    def get_barrier_pattern_for_country(self, country: str) -> Record | None:
        ...

    # -- country_bottleneck_profile.csv ------------------------------------
    @abstractmethod
    def get_bottleneck_profiles(self) -> list[Record]:
        ...

    @abstractmethod
    def get_bottleneck_profile_for_country(self, country: str) -> Record | None:
        ...

    # -- bottleneck_type_summary.csv ---------------------------------------
    @abstractmethod
    def get_bottleneck_type_summary(self) -> list[Record]:
        ...

    # -- gap_barrier_correlation.csv ----------------------------------------
    @abstractmethod
    def get_gap_barrier_correlation(self) -> list[Record]:
        ...

    # -- sensitivity_analysis.csv --------------------------------------------
    @abstractmethod
    def get_sensitivity_analysis(self) -> list[Record]:
        ...

    # -- country_indicator_distribution.csv -----------------------------------
    @abstractmethod
    def get_country_indicator_distribution(self) -> list[Record]:
        ...

    # -- country_pattern_profile.csv -------------------------------------------
    @abstractmethod
    def get_country_pattern_profiles(self) -> list[Record]:
        ...

    @abstractmethod
    def get_country_pattern_profile_for_country(self, country: str) -> Record | None:
        ...
