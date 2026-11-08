"""Error classes for corpus module."""

from package._error import ToolInputError


class SQLTimeOutError(ToolInputError):
    """SQL query took too long to run (timeout)."""