=========
TSNetPlus
=========

.. contents::
   :local:

About this fork
===============

TSNetPlus is a fork of `TSNet <https://github.com/glorialulu/TSNet>`_, the
open-source Python package for transient simulation in water distribution
networks developed at the WATSUP group, University of Texas at Austin.

The transient simulation model, the network representation, the transient
event handling (valve operations, pump shutdowns, bursts and leaks) and the
friction models are those of TSNet. The purpose of the fork is to make the
transient simulation substantially faster without changing what the user of
the package has to write, and to make the numerical kernels swappable so that
speed and numerical precision can be traded explicitly.

TSNetPlus is distributed under the same MIT licence as TSNet and retains the
original copyright notice (see ``LICENSE``).

Attribution
-----------

* Original TSNet: Lu Xing and Lina Sela (University of Texas at Austin), with
  contributions from the WATSUP group.
* TSNetPlus: Tomasz Janus (University of Manchester) and Hector Duque (De
  Montfort University).

The original TSNet reference publication remains the reference for the
simulation model implemented here:

Xing, Lu, and Lina Sela. "Transient simulations in water distribution networks:
TSNet python package." Advances in Engineering Software 149 (2020): 102884.

What changed
============

Package name
------------

The package is distributed and imported as ``tsnetplus`` instead of ``tsnet``.
This is a breaking change::

    # TSNet
    import tsnet

    # TSNetPlus
    import tsnetplus

Swappable simulation kernels
----------------------------

The numerical work of the solver is performed by a *kernel*. In TSNet there was
a single, pure-Python kernel. In TSNetPlus the kernel is selected with
:class:`tsnetplus.backends.ComputeBackend`:

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Backend
     - Module
     - Notes
   * - ``PYTHON``
     - ``tsnetplus.kernels.python``
     - Optimised pure-Python kernel. Default, no extra dependency.
   * - ``NUMBA``
     - ``tsnetplus.kernels.numba``
     - Just-in-time compiled kernel. Requires the optional ``numba``
       dependency.
   * - ``ORIGINAL``
     - ``tsnetplus.kernels.python_original``
     - The unmodified upstream kernel, retained as a reference implementation
       for benchmarking and regression testing.

The kernels are selected per call, which makes it possible to run the same
transient event with different kernels and compare the results::

    import tsnetplus
    from tsnetplus.backends import ComputeBackend

    tm = tsnetplus.network.TransientModel('networks/Tnet0.inp')
    tm.set_time(120.0, 0.01)
    tm.valve_closure('3', [0.4, 0.0, 0.0, 1.0])
    tm = tsnetplus.simulation.initialize(tm, 0.0, 'PDD', ComputeBackend.NUMBA)
    tm = tsnetplus.simulation.MOCSimulator(tm, 'no', 'steady', ComputeBackend.NUMBA)

For the Numba backend the JIT kernels are compiled once during initialisation
(see ``tsnetplus.kernels.numba.precompile``), so that compilation does not
happen in the middle of the simulation.

Numerical agreement
-------------------

The optimised kernels do not reproduce the upstream kernel bit for bit. The
upstream kernel solves the inner-node system one node at a time in Python,
whereas the optimised kernels operate on all nodes with array operations and,
in the Numba kernel, with compiled loops. The resulting differences are small,
but they are not zero, and they are reported rather than hidden: the
:doc:`performance` page lists the maximum absolute and relative deviation of
the computed pressure head for every benchmarked network.

Documentation of the kernel modules
-----------------------------------

The three kernel subpackages are internal implementation details and are not
included in the generated API documentation; they are three implementations of
the same routines, and documenting all of them would be redundant. The public
entry points for selecting a kernel are :class:`tsnetplus.backends.ComputeBackend`
and the ``kernel`` argument of :func:`tsnetplus.simulation.initialize` and
:class:`tsnetplus.simulation.MOCSimulator`.

Versioning
----------

Because the import name changed, TSNetPlus follows its own version series. The
first release of the fork is 0.4.0; the upstream series ended at 0.3.1. The
release history is in ``HISTORY.rst``.

What did not change
===================

* The Method of Characteristics (MOC) formulation of the transient simulation.
* The network model built from EPANET INP files.
* The supported transient events and the way they are specified.
* The available friction models (steady, quasi-steady and unsteady).
* The MIT licence and the original copyright notice.