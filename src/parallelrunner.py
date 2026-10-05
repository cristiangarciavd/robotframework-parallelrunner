"""
Deprecated compatibility shim for the pre-0.2.0 import paths.

Old style (still works, emits a DeprecationWarning)::

    Library    parallelrunner.parallel_library.ParallelLibrary

New style::

    Library    ParallelRunner

Why a single-file module instead of a ``parallelrunner/`` package: Windows and
macOS filesystems are case-insensitive by default, so a ``parallelrunner/``
directory cannot live next to ``ParallelRunner/``. Registering the submodule
in ``sys.modules`` makes ``parallelrunner.parallel_library`` importable anyway.
"""

import sys
import warnings

from ParallelRunner import ParallelLibrary, ParallelRunner, ParallelTaskError, __version__
from ParallelRunner import parallel_library

warnings.warn(
    "Importing 'parallelrunner' is deprecated and will be removed in a future "
    "release; use 'Library    ParallelRunner' (or 'from ParallelRunner import "
    "ParallelRunner') instead.",
    DeprecationWarning,
    stacklevel=2,
)

sys.modules[__name__ + ".parallel_library"] = parallel_library

__all__ = ["ParallelRunner", "ParallelLibrary", "ParallelTaskError", "__version__", "parallel_library"]
