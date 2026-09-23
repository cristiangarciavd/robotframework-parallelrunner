"""
parallelrunner - Thread-based parallel execution for Robot Framework test cases.

This package exposes the ParallelLibrary Robot Framework library, which lets a
single test case fan out a keyword (or Python method) across a thread pool
while keeping log.html clean via a buffer-and-replay mechanism.

Typical usage in a Robot Framework suite::

    *** Settings ***
    Library    parallelrunner.parallel_library.ParallelLibrary

See ARCHITECTURE.md and docs/ in the project repository for details.
"""

from .parallel_library import ParallelLibrary, ParallelTaskError

__version__ = "0.1.0"

__all__ = ["ParallelLibrary", "ParallelTaskError", "__version__"]
