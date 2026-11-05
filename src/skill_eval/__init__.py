"""Evaluate agent skills before sharing them with teams.

The package follows a hexagonal layout: ``domain`` holds the pure evaluation
method, ``application`` the use cases and their ports, ``adapters`` the
input/output implementations, and ``cli`` the command-line entry point.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("skill-eval")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0.0.0+unknown"
