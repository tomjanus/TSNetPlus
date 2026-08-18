""" """
from typing import TypeAlias, Literal
from ..backends import ComputeBackend
from ..network.model import TransientModel

Engine: TypeAlias = Literal["DD", "PDD"]

    
def MOCSimulator(
        tm: TransientModel,
        results_obj='results',
        friction='steady',
        kernel: ComputeBackend = ComputeBackend.PYTHON):
    """ """
    if kernel == ComputeBackend.PYTHON:
        from tsnet.kernels.python import MOCSimulator
        return MOCSimulator(tm = tm, results_obj = results_obj, friction = friction)
    if kernel == ComputeBackend.NUMBA:
        from tsnet.kernels.numba import MOCSimulator, precompile
        precompile()
        return MOCSimulator(tm = tm, results_obj = results_obj, friction = friction)
    raise ValueError(
        f"Unsupported backend {kernel.value!r}."
    )


def initialize(
        tm: TransientModel,
        t0: float,
        engine: Engine='DD',
        kernel: ComputeBackend = ComputeBackend.PYTHON) -> TransientModel:
    """Caller for the
    
    Parameters
    ----------
    tm : tsnet.network.model.TransientModel
        Simulated network
    t0 : float
        time to calculate initial condition
    engine : Engine
        steady state calculation engine:
        DD: demand driven;
        PDD: pressure dependent demand,
        by default DD

    Returns
    -------
    tm : tsnet.network.model.TransientModel
        Network with updated parameters
    """
    if kernel == ComputeBackend.PYTHON:
        from tsnet.kernels.python import initialize
        return initialize(tm = tm, t0 = t0, engine = engine)
    if kernel == ComputeBackend.NUMBA:
        from tsnet.kernels.numba import initialize
        return initialize(tm = tm, t0 = t0, engine = engine)
    raise ValueError(
        f"Unsupported backend {kernel.value!r}."
    )
