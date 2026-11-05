"""Email normalization, shared by the models, schemas, and services."""


def normalize_email(email: str) -> str:
    """Return the one stored form of an address: no surrounding spaces, all lowercase."""
    return email.strip().lower()
