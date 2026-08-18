""" """
import numpy as np
from .simulator import MOCSimulator
from .initialize import initialize
from .solver import _inner_quasisteady, _inner_steady, _inner_unsteady


def precompile() -> None:
    """Precompile the Numba-compiled solver kernels.

    Executes each JIT-compiled kernel once using representative input
    arrays so that Numba compiles the required signatures before the
    main simulation begins. This moves the one-time JIT compilation
    overhead out of the simulation's critical execution path.

    The input values are only used to trigger compilation; their
    numerical results are intentionally ignored.

    Notes
    -----
    This function should be called once during initialization when the
    Numba backend is selected.
    """
    H = np.array([10.0, 10.0, 10.0, 10.0], dtype=np.float64)
    V = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float64)
    dVdx = np.zeros(3, dtype=np.float64)
    dVdt = np.zeros(4, dtype=np.float64)
    _inner_steady(0.02, 0.3, 1000.0, 0.0, 0.1, H, V)
    _inner_quasisteady(0.3, 1000.0, 0.0, 1e-3, 0.1, H, V)
    _inner_unsteady(0.3, 1000.0, 0.0, 1e-3, 0.1, H, V, dVdx, dVdt)


__all__ = [
    "MOCSimulator",
    "initialize"
    "precompile"
    ]
