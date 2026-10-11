"""Error classes for corpus module."""

from ..base._error import ToolInputError


class SQLTimeOutError(ToolInputError):
    """SQL query took too long to run (timeout)."""