"""Shared error classes for the package."""


class ToolInputError(ValueError):
    """Caller gave invalid input (bad filter, unsafe SQL, unknown domain...)."""
