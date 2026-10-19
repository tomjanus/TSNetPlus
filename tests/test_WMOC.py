"""Smoke tests for the `tsnetplus` package.

These tests exercise the public API on the small network shipped with the
benchmark suite, so that a broken installation or a broken solver is caught
quickly.
"""

from pathlib import Path

import numpy as np

import tsnetplus
from tsnetplus.backends import ComputeBackend

NETWORK = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "networks"
    / "Tnet0.inp"
)

# A short simulation is enough to exercise the whole solver.
SIMULATION_PERIOD = 2.0
TIME_STEP = 0.01


def run_simulation(kernel: ComputeBackend):
    """Run a short valve-closure transient simulation with ``kernel``."""
    tm = tsnetplus.network.TransientModel(NETWORK)
    tm.set_wavespeed(1200.0)
    tm.set_time(SIMULATION_PERIOD, TIME_STEP)
    tm.valve_closure("3", [0.4, 0.0, 0.0, 1.0])
    tm = tsnetplus.simulation.initialize(tm, 0.0, "PDD", kernel)
    return tsnetplus.simulation.MOCSimulator(tm, "no", "steady", kernel)


def test_package_metadata():
    """The package exposes a version and the two public helpers."""
    assert isinstance(tsnetplus.__version__, str)
    assert callable(tsnetplus.configure_logging)


def test_compute_backend_members():
    """All documented kernels are selectable."""
    for name in ("PYTHON", "NUMBA", "ORIGINAL"):
        assert hasattr(ComputeBackend, name)


def test_python_kernel_produces_results():
    """The default kernel simulates the network and returns results."""
    tm = run_simulation(ComputeBackend.PYTHON)

    assert len(tm.simulation_timestamps) > 0
    head = np.asarray(tm.get_node("2").head, dtype=float)
    assert head.size > 0
    assert np.isfinite(head).any()
    assert np.nanmax(head) > 0.0


def test_backends_agree():
    """The optimised kernels agree with the upstream kernel closely.

    The kernels are not bit-identical (see the performance page of the
    documentation), so the comparison uses a tolerance rather than exact
    equality.
    """
    reference = run_simulation(ComputeBackend.ORIGINAL)

    for kernel in (ComputeBackend.PYTHON, ComputeBackend.NUMBA):
        tm = run_simulation(kernel)
        expected = np.asarray(reference.get_node("2").head, dtype=float)
        actual = np.asarray(tm.get_node("2").head, dtype=float)

        assert expected.shape == actual.shape
        finite = np.isfinite(expected) & np.isfinite(actual)
        assert finite.any()
        np.testing.assert_allclose(
            actual[finite],
            expected[finite],
            rtol=1e-3,
            atol=0.1,
            err_msg=f"{kernel.value} deviates from the original kernel",
        )
