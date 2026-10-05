"""
ParallelRunner - Thread-based parallel execution for Robot Framework test cases.

Lets a single test case fan out a keyword (or Python method) across a thread
pool while keeping log.html clean via a buffer-and-replay mechanism.

Typical usage in a Robot Framework suite::

    *** Settings ***
    Library    ParallelRunner

Keyword documentation:
https://cristiangarciavd.github.io/robotframework-parallelrunner/ParallelRunner.html
"""

from .parallel_library import ParallelLibrary, ParallelRunner, ParallelTaskError
from .version import __version__

__all__ = ["ParallelRunner", "ParallelLibrary", "ParallelTaskError", "__version__"]
