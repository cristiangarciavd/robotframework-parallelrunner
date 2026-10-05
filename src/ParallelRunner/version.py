"""Single source of truth for the library version.

The version lives only in ``pyproject.toml`` (bump it with ``poetry version
patch|minor|major``). At runtime it is read back from the installed
distribution's metadata, so ``__version__`` / ``ROBOT_LIBRARY_VERSION`` can
never drift from what was published to PyPI.
"""

from importlib.metadata import PackageNotFoundError, version as _dist_version

DISTRIBUTION_NAME = "robotframework-parallelrunner"

try:
    __version__ = _dist_version(DISTRIBUTION_NAME)
except PackageNotFoundError:  # running from a source checkout that was never installed
    __version__ = "0.0.0+unknown"
