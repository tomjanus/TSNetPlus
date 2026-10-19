=======
History
=======

0.4.0 (unreleased)
------------------
First release of **TSNetPlus**, a fork of `TSNet
<https://github.com/glorialulu/TSNet>`_ (upstream release 0.3.1) whose main
purpose is faster transient simulation.

1. Renamed the package from ``tsnet`` to ``tsnetplus``. **This is a breaking
   change**: ``import tsnet`` becomes ``import tsnetplus``.
2. Added pluggable simulation kernels selected with
   ``tsnetplus.backends.ComputeBackend``: the optimised pure-Python kernel,
   the Numba just-in-time compiled kernel (optional dependency, available as
   the ``speedups`` extra) and the unmodified upstream kernel kept as
   ``ComputeBackend.ORIGINAL`` reference implementation.
3. Added JIT kernel pre-compilation so that Numba compilation happens during
   initialisation instead of during the simulation.
4. Added the benchmarking suite ``benchmarks/benchmark_backends.py`` together
   with the measured results in ``benchmarks/results/`` and in the
   performance page of the documentation.
5. Fixed ``configure_logging()``, which configured a ``tsnet`` logger instead
   of the ``tsnetplus`` logger used by the package modules and therefore had
   no effect on the package log messages.
6. Dropped Python 3.6 and 3.7 support; the package now requires Python 3.10
   or newer.
7. Updated the documentation, which builds with Sphinx again, and publish it
   at https://tomjanus.github.io/TSNetPlus through GitHub Pages.

The results of the optimised kernels agree with the upstream reference
implementation to within the deviations measured in the performance
documentation; they are not bit-identical.

The history below documents the upstream TSNet releases.

0.1.0 (2019-08-15)
------------------

* First release on PyPI.

0.1.1 (2019-09-21)
------------------

0.1.2 (2020-01-20)
------------------
1. Fixed bugs about dead end and single pipe.
2. Added plot and change detection methods.

0.2.0 (2020-4-23)
-------------------
1. Added quasi-steady and unsteady friction model.
2. Added open and closed surge tanks.
3. Added demand-pulse simulation.
4. Updated docs.

0.2.1 (2020-09-09)
-------------------
1. Fixed minor bugs about valve default settings.
2. Updated documentation.
3. Updated WNTR compatibility.

0.2.2 (2020-09-24)
-------------------
1. Updated WNTR compatibility.

0.2.3 (2021-11-12)
-------------------
1. Only support WNTR version up until 0.3.0

0.2.4 (2022-06-17)
-------------------
1. fix minor issues regarding reporting messages
2. Only support WNTR version up until 0.2.3.

0.3.0 (2023-02-22)
-------------------
1. Support WNTR version 1.0.0
2. Test on python 3.10 and 3.11.
3. Drop supports for Python 3.6 and 3.7
