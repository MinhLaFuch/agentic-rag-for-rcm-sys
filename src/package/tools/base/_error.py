"""Error classes for tools base module."""


class ToolInputError(ValueError):
    """Caller gave invalid input (bad filter, unsafe SQL, unknown domain...)."""
