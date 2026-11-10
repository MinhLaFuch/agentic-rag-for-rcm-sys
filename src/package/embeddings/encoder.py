"""
Encoder compatibility shim for TextEncoder.
"""

from __future__ import annotations

from .text_encoder import TextEncoder


class Encoder(TextEncoder):
    """TextEncoder alias matching file name to satisfy atomic package conventions."""
    pass
