# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Bento application package."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("bento")
except PackageNotFoundError:
    __version__ = "0.1.0"
