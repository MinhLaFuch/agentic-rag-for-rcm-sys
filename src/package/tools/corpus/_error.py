"""Error classes for corpus module."""

from ..base import ToolInputError


class SQLTimeOutError(ToolInputError):
    """SQL query took too long to run (timeout)."""