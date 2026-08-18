"""
Kernel backend selection utilities.

This module provides a unified interface for selecting numerical kernels
implemented using different computational backends:

- Pure Python: always available fallback implementation.
- Numba: JIT-compiled implementation when Numba is installed.
- Cython: compiled extension implementation when available.

The selected backend is returned as a :class:`KernelSet`, which provides
the numerical routines required by the transient solver.
"""
from __future__ import annotations
from .types import KernelSet
from .cython import HAS_CYTHON
from ..config import ComputeBackend

def _select_auto_backend() -> ComputeBackend:
    """
    Select the fastest available computational backend.

    Returns
    -------
    ComputeBackend
        Available backend selected according to priority:

        1. Cython
        2. Numba
        3. Pure Python
    """
    if HAS_CYTHON:
        return ComputeBackend.CYTHON
    if _numba_available():
        return ComputeBackend.NUMBA
    return ComputeBackend.PYTHON


def _numba_available() -> bool:
    """
    Check whether Numba is installed.

    Returns
    -------
    bool
        ``True`` if Numba can be imported, otherwise ``False``.
    """
    try:
        import numba  # noqa: F401
    except ImportError:
        return False
    return True
