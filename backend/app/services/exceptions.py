class CountryNotFoundError(Exception):
    def __init__(self, country: str):
        self.country = country
        super().__init__(f"Country not found: {country}")


class InvalidComparisonRequestError(Exception):
    """Raised when a comparison request does not select 2-3 countries."""
