"""Benchmark the TSNetPlus simulation backends.

The script compares the wall-clock execution time of the three transient
simulation kernels shipped with TSNetPlus:

``original``
    The unmodified kernel inherited from the upstream `TSNet
    <https://github.com/glorialulu/TSNet>`_ package. This is the reference
    implementation against which the speed-up is measured.
``python``
    The optimised pure-Python kernel.
``numba``
    The Numba just-in-time compiled kernel (requires ``numba``).

Every network is benchmarked with the transient event shipped with the
corresponding example in ``examples/`` (valve closure, pump shutdown or pipe
burst), so the measured times correspond to a realistic transient simulation.

For each network and backend the script runs one warm-up simulation
(discarded, so that interpreter warm-up and Numba JIT compilation are excluded
from the reported timings) followed by ``--repeats`` timed simulations, and
reports the median wall-clock time.

Numerical agreement
-------------------
The optimised backends are not bit-identical to the reference implementation:
the ``original`` kernel solves the inner-node system one node at a time in
Python, whereas the optimised kernels operate on all nodes with array
operations. The differences are reported as a maximum absolute and relative
deviation of the pressure head over all nodes and time steps, together with
the magnitude of the head itself, so that the size of the deviation can be
judged against the physical scale of the result. Results are written as a CSV
file under ``benchmarks/results/``.

Examples
--------
Run the full benchmark suite::

    python benchmarks/benchmark_backends.py

Run a single network with more repetitions::

    python benchmarks/benchmark_backends.py --networks Tnet0 --repeats 5
"""

from __future__ import annotations

import argparse
import csv
import platform
import statistics
import time
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Callable

import numpy as np

import tsnetplus
from tsnetplus.backends import ComputeBackend

NETWORKS_DIR = Path(__file__).parent.resolve() / "networks"
RESULTS_DIR = Path(__file__).parent.resolve() / "results"

DEFAULT_FRICTION = "steady"
DEFAULT_DT = 0.01
DEFAULT_REPEATS = 3

REFERENCE_BACKEND = ComputeBackend.ORIGINAL
BACKENDS = (
    ComputeBackend.ORIGINAL,
    ComputeBackend.PYTHON,
    ComputeBackend.NUMBA,
)


@dataclass(frozen=True)
class Scenario:
    """Transient event applied to a benchmark network.

    The event and solver settings mirror the corresponding example in
    ``examples/``, so the measured times correspond to realistic transient
    simulations of the shipped networks. ``dt`` of ``None`` selects the
    largest time step allowed by the Courant condition of the network, as
    the examples do.
    """

    network: str
    description: str
    tf: float
    setup: Callable[[object], None]
    dt: float | None = None
    wavespeed: float | np.ndarray = 1200.0
    engine: str = "PDD"
    friction: str = DEFAULT_FRICTION


def _valve_closure_tnet0(tm) -> None:
    tm.valve_closure("3", [0.4, 0.0, 0.0, 1.0])


def _valve_closure_tnet1(tm) -> None:
    tm.valve_closure("VALVE", [1.0, 5.0, 0.0, 2.0])


def _pump_shutdown_tnet2(tm) -> None:
    tm.pump_shut_off("PUMP2", [1.0, 1.0, 0.0, 1.0])


def _pipe_burst_tnet3(tm) -> None:
    tm.add_burst("JUNCTION-20", 1.0, 1.0, 0.01)


def _tnet3_wavespeed(num_pipes: int) -> np.ndarray:
    """Random pipe wave speeds, reproducible via a fixed seed.

    ``examples/Tnet3_burst_leak.py`` draws the wave speeds from a normal
    distribution. A fixed seed is used here so that repeated benchmark runs
    are comparable.
    """
    return np.random.default_rng(0).normal(1200.0, 100.0, size=num_pipes)


SCENARIOS: dict[str, Scenario] = {
    "Tnet0": Scenario(
        network="Tnet0",
        description="valve closure",
        tf=120.0,
        setup=_valve_closure_tnet0,
        dt=DEFAULT_DT,
    ),
    "Tnet1": Scenario(
        network="Tnet1",
        description="valve closure",
        tf=120.0,
        setup=_valve_closure_tnet1,
        engine="DD",
    ),
    "Tnet2": Scenario(
        network="Tnet2",
        description="pump shutdown",
        tf=20.0,
        setup=_pump_shutdown_tnet2,
        engine="DD",
    ),
    "Tnet3": Scenario(
        network="Tnet3",
        description="pipe burst",
        tf=20.0,
        setup=_pipe_burst_tnet3,
        wavespeed=-1.0,  # sentinel: seeded random wave speeds
    ),
}

DEFAULT_NETWORKS = tuple(SCENARIOS)


def build_model(scenario: Scenario, kernel: ComputeBackend):
    """Create, initialise and simulate a transient model for one scenario.

    Parameters
    ----------
    scenario
        Network, transient event and solver settings to use.
    kernel
        Simulation backend to execute the transient simulation with.

    Returns
    -------
    TransientModel
        Simulated model whose results can be compared between backends.
    """
    inp_file = NETWORKS_DIR / f"{scenario.network}.inp"
    tm = tsnetplus.network.TransientModel(inp_file)

    wavespeed: float | np.ndarray = scenario.wavespeed
    if isinstance(wavespeed, float) and wavespeed < 0:
        wavespeed = _tnet3_wavespeed(tm.num_pipes)
    tm.set_wavespeed(wavespeed)
    tm.set_time(scenario.tf, scenario.dt)

    scenario.setup(tm)

    tm = tsnetplus.simulation.initialize(tm, 0.0, scenario.engine, kernel)
    return tsnetplus.simulation.MOCSimulator(
        tm, "no", scenario.friction, kernel
    )


def time_backend(scenario: Scenario, kernel: ComputeBackend, repeats: int):
    """Time ``repeats`` simulations of one backend.

    A single warm-up run is executed and discarded before timing, so that
    interpreter warm-up, caching effects and (for Numba) JIT compilation are
    excluded from the reported timings.

    Parameters
    ----------
    scenario
        Network, transient event and solver settings to use.
    kernel
        Backend to time.
    repeats
        Number of timed simulations.

    Returns
    -------
    tuple
        Median wall-clock time in seconds and the model produced by the final
        run.
    """
    build_model(scenario, kernel)  # warm-up, discarded

    timings = []
    model = None
    for _ in range(repeats):
        start = time.perf_counter()
        model = build_model(scenario, kernel)
        timings.append(time.perf_counter() - start)
    return statistics.median(timings), model


def head_deviation(reference, other) -> tuple[float, float, float]:
    """Compare the pressure head of two simulated models.

    Parameters
    ----------
    reference
        Model simulated with the reference (upstream) kernel.
    other
        Model simulated with the kernel under test.

    Returns
    -------
    tuple
        Maximum absolute deviation [m], maximum deviation relative to the
        magnitude of the reference head, and the maximum reference head
        [m]. Empty arrays and non-finite entries are ignored.
    """
    worst_abs = 0.0
    worst_rel = 0.0
    head_scale = 0.0
    for node_id in reference.nodes:
        x = np.asarray(reference.get_node(node_id).head, dtype=float)
        y = np.asarray(other.get_node(node_id).head, dtype=float)
        if x.shape != y.shape or x.size == 0:
            continue
        finite = np.isfinite(x) & np.isfinite(y)
        if not finite.any():
            continue
        deviation = np.abs(x[finite] - y[finite])
        magnitude = np.abs(x[finite])
        worst_abs = max(worst_abs, float(deviation.max()))
        if magnitude.max() > 0:
            worst_rel = max(worst_rel, float((deviation / magnitude).max()))
        head_scale = max(head_scale, float(magnitude.max()))
    return worst_abs, worst_rel, head_scale


def cpu_model() -> str:
    """Return a human readable CPU model, falling back to the machine type."""
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:  # pragma: no cover - not a Linux machine
        pass
    return platform.processor() or platform.machine()


def environment_info() -> dict[str, str]:
    """Collect the environment the benchmark was executed in."""
    versions = {"python": platform.python_version(), "numpy": np.__version__}
    for name in ("numba", "wntr"):
        try:
            imported = __import__(name)
            versions[name] = imported.__version__
        except ImportError:  # pragma: no cover - numba is optional
            versions[name] = "not installed"

    return {
        "date": date.today().isoformat(),
        "platform": platform.platform(),
        "cpu": cpu_model(),
        **versions,
        "tsnetplus": tsnetplus.__version__,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Benchmark TSNetPlus backends."
    )
    parser.add_argument(
        "--networks",
        nargs="+",
        default=list(DEFAULT_NETWORKS),
        choices=list(DEFAULT_NETWORKS),
        help="Networks to benchmark (default: %(default)s).",
    )
    parser.add_argument(
        "--friction",
        default=DEFAULT_FRICTION,
        choices=["steady", "quasi-steady", "unsteady"],
        help="Friction model (default: %(default)s).",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=DEFAULT_REPEATS,
        help="Number of timed runs per backend (default: %(default)s).",
    )
    parser.add_argument(
        "--tf",
        type=float,
        default=None,
        help="Override the simulation end time in seconds for every network.",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=None,
        help="Override the time step in seconds for every network.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the benchmark suite and write the results to a CSV file."""
    args = parse_args(argv)
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")

    info = environment_info()
    print("Environment")
    for key, value in info.items():
        print(f"  {key}: {value}")

    rows: list[dict[str, object]] = []
    for name in args.networks:
        scenario = SCENARIOS[name]
        if args.tf is not None or args.dt is not None:
            scenario = replace(
                scenario,
                tf=args.tf if args.tf is not None else scenario.tf,
                dt=args.dt if args.dt is not None else scenario.dt,
                friction=args.friction,
            )
        print(
            f"\nBenchmarking {name} ({scenario.description}, "
            f"tf={scenario.tf} s, dt={scenario.dt or 'auto'} s, "
            f"friction={args.friction})"
        )

        medians: dict[ComputeBackend, float] = {}
        models = {}
        for kernel in BACKENDS:
            median, model = time_backend(scenario, kernel, args.repeats)
            medians[kernel] = median
            models[kernel] = model
            print(f"  {kernel.value:<9} {median:8.3f} s")

        reference_time = medians[REFERENCE_BACKEND]
        deviations: dict[ComputeBackend, tuple[float, float, float]] = {}
        for kernel in BACKENDS:
            if kernel is REFERENCE_BACKEND:
                continue
            deviations[kernel] = head_deviation(
                models[REFERENCE_BACKEND], models[kernel]
            )

        for kernel in BACKENDS:
            worst_abs, worst_rel, scale = deviations.get(kernel, ("", "", ""))
            rows.append(
                {
                    **info,
                    "network": scenario.network,
                    "event": scenario.description,
                    "friction": args.friction,
                    "tf": scenario.tf,
                    "dt": scenario.dt if scenario.dt is not None else "auto",
                    "repeats": args.repeats,
                    "backend": kernel.value,
                    "median_seconds": round(medians[kernel], 4),
                    "speedup_vs_original": round(
                        reference_time / medians[kernel], 2
                    ),
                    "max_head_deviation_m": (
                        f"{worst_abs:.3e}" if worst_abs != "" else ""
                    ),
                    "max_head_deviation_rel": (
                        f"{worst_rel:.2e}" if worst_rel != "" else ""
                    ),
                    "head_scale_m": f"{scale:.1f}" if scale != "" else "",
                }
            )

        for kernel, (worst_abs, worst_rel, scale) in deviations.items():
            print(
                f"  {kernel.value}: max head deviation from original "
                f"{worst_abs:.3e} m ({worst_rel:.2e} relative, "
                f"head up to {scale:.1f} m)"
            )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output = RESULTS_DIR / f"{date.today().isoformat()}_backends.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nResults written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
