.. _performance:

===========
Performance
===========

.. contents::
   :local:

Why
===

The Method of Characteristics (MOC) solver of TSNet is dominated by the
inner-node computations performed at every time step. The upstream
implementation advances the network one node at a time, in interpreted Python,
so the cost of a transient simulation grows linearly with the number of time
steps and with the number of nodes, and a single simulation of a real network
can take tens of seconds. That is inconvenient for the use cases TSNet was
written for, such as sensor placement, event detection and network
calibration, where hundreds or thousands of simulations are run in sequence.

How the speed-up was obtained
=============================

TSNetPlus does not change the physics. The MOC formulation, the friction
models, the boundary conditions and the transient events are those of TSNet.
The speed-up comes from restructuring the numerical kernels, and the kernel is
now selectable at run time through :class:`tsnetplus.backends.ComputeBackend`:

Optimised pure-Python kernel
----------------------------

The inner-node computations are expressed as operations on whole arrays of
nodes instead of as loops over individual nodes. This keeps the kernel pure
Python, so there is no compilation step and no extra dependency, but it
removes a large amount of interpreter overhead.

Numba just-in-time compiled kernel
----------------------------------

The same array-based formulation is additionally decorated with ``numba.njit``,
which compiles the inner-node routines to machine code. The compiled kernels
are triggered once at the start of a simulation
(:func:`tsnetplus.kernels.numba.precompile`), so that the JIT compilation does
not happen in the middle of the time loop.

The unmodified upstream kernel
------------------------------

The upstream kernel is kept as
:class:`~tsnetplus.backends.ComputeBackend.ORIGINAL`
(``tsnetplus.kernels.python_original``). It is the reference implementation:
it is used for regression testing and as the baseline of the benchmark below,
and it remains available for users who need to reproduce published TSNet
results exactly.

Benchmark
=========

The benchmark is implemented in ``benchmarks/benchmark_backends.py``:

.. code-block:: console

    $ python benchmarks/benchmark_backends.py

Protocol
--------

* Networks: ``Tnet0`` (valve closure), ``Tnet1`` (valve closure), ``Tnet2``
  (pump shutdown) and ``Tnet3`` (pipe burst), the networks shipped in
  ``benchmarks/networks`` with the events of the corresponding scripts in
  ``examples``.
* Friction model: steady friction, one common setting for all backends.
* Each network and backend is run once as a warm-up (discarded, so that
  interpreter warm-up and JIT compilation are not counted) and then three more
  times; the reported time is the median of the three timed runs.
* Time step: ``0.01 s`` for ``Tnet0``, the largest Courant-limited time step of
  the network for the other networks, as in the example scripts.
* Wave speeds: ``1200 m/s`` everywhere except ``Tnet3``, for which the random
  wave speeds of the example are drawn with a fixed seed so that the runs are
  reproducible.

.. list-table:: Measured execution time, median of three timed runs
   :header-rows: 1
   :widths: 22 12 22 22 22 14

   * - Network (event)
     - Simulation
     - ``ORIGINAL`` (upstream)
     - ``PYTHON``
     - ``NUMBA``
     - Speed-up
   * - Tnet0 (valve closure)
     - 120 s, dt = 0.01 s
     - 11.24 s (1.00x)
     - 10.40 s (1.08x)
     - **0.86 s (13.06x)**
     - 13.1x
   * - Tnet1 (valve closure)
     - 120 s, auto dt
     - 0.29 s (1.00x)
     - 0.28 s (1.06x)
     - **0.27 s (1.11x)**
     - 1.1x
   * - Tnet2 (pump shutdown)
     - 20 s, auto dt
     - 27.76 s (1.00x)
     - 25.35 s (1.10x)
     - **9.14 s (3.04x)**
     - 3.0x
   * - Tnet3 (pipe burst)
     - 20 s, auto dt
     - 29.92 s (1.00x)
     - 28.24 s (1.06x)
     - **16.22 s (1.84x)**
     - 1.8x

Maximum deviation of the pressure head from the ``ORIGINAL`` kernel, over all
nodes and all time steps:

.. list-table:: Numerical agreement with the upstream kernel
   :header-rows: 1
   :widths: 40 30 30

   * - Network
     - Maximum absolute deviation
     - Relative to the maximum head
   * - Tnet0 (head up to 761.9 m)
     - 0.041 m
     - 5.5e-05
   * - Tnet1 (head up to 216.4 m)
     - 0.026 m
     - 1.6e-04
   * - Tnet2 (head up to 93.1 m)
     - 0.003 m
     - 6.8e-05
   * - Tnet3 (head up to 355.7 m)
     - 0.033 m
     - 1.5e-04

Environment of the run reported above:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - CPU
     - 11th Gen Intel(R) Core(TM) i9-11950H @ 2.60GHz
   * - Operating system
     - Linux 7.0.0-34-generic, x86_64, glibc 2.39
   * - Python
     - 3.12.7
   * - NumPy
     - 2.5.2
   * - Numba
     - 0.68.0
   * - WNTR
     - 1.5.0
   * - TSNetPlus
     - 0.4.0

The raw data of this run is version controlled in
``benchmarks/results/2026-10-19_backends.csv``.

Numerical agreement
-------------------

The optimised kernels are not bit-identical to the upstream kernel: the
upstream kernel solves the inner-node system one node at a time, whereas the
optimised kernels work on arrays of nodes and, in the Numba kernel, on
compiled loops. The table therefore also reports the largest deviation of the
pressure head over all nodes and all time steps, together with the magnitude
of the head itself, so that the deviation can be judged against the physical
scale of the result.

The deviations are of the order of tens of millimetres on heads of several
hundred metres, that is around ``1e-4`` in relative terms. Users who need to
reproduce published TSNet results exactly can select the ``ORIGINAL`` kernel.

Reproducing the measurement
---------------------------

The raw results of the run reported above, including the exact environment, are
version controlled in ``benchmarks/results/``. To reproduce them:

.. code-block:: console

    $ pip install ".[speedups]"
    $ python benchmarks/benchmark_backends.py --repeats 3

The absolute times depend on the machine; the speed-up ratios are the
meaningful quantity to compare across machines.

Caveats
-------

* The measurements were taken on a single machine and a single run of the
  benchmark suite. They are not a formal benchmark study.
* Only the steady friction model was measured. The relative speed-up of the
  Numba kernel is expected to be larger for the quasi-steady and unsteady
  friction models, which solve a larger inner-node system, but this has not
  been measured.
* Total runtime includes the steady-state initialisation performed by WNTR,
  which is identical for all backends and therefore dilutes the speed-up
  reported for the transient simulation alone.