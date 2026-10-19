TSNetPlus
=========

.. image:: https://img.shields.io/github/license/tomjanus/TSNetPlus
        :target: https://github.com/tomjanus/TSNetPlus/blob/master/LICENSE
        :alt: GitHub license

.. image:: https://img.shields.io/badge/fork%20of-TSNet-blue?logo=github
        :target: https://github.com/glorialulu/TSNet
        :alt: Fork of TSNet

.. image:: https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue?logo=python
        :alt: Supported Python versions

.. image:: https://github.com/tomjanus/TSNetPlus/actions/workflows/ci.yml/badge.svg
        :target: https://github.com/tomjanus/TSNetPlus/actions/workflows/ci.yml
        :alt: CI status

.. image:: https://github.com/tomjanus/TSNetPlus/actions/workflows/docs.yml/badge.svg
        :target: https://github.com/tomjanus/TSNetPlus/actions/workflows/docs.yml
        :alt: Documentation build status

**TSNetPlus** is a fork of `TSNet <https://github.com/glorialulu/TSNet>`_,
the open-source Python package that performs transient simulation in water
distribution networks using the Method of Characteristics (MOC).

TSNetPlus keeps the transient simulation model of TSNet and focuses on making
it **much faster to run**. The simulation kernels are pluggable, and the
Numba just-in-time compiled kernel reduces the execution time of a transient
simulation by between 1.1x and 13x on the benchmark networks shipped with the
package (see `Performance`_). The results remain in agreement with the
upstream reference implementation: the measured deviations are reported in the
documentation.

* Free software: MIT license
* GitHub: https://github.com/tomjanus/TSNetPlus.git
* Upstream project: https://github.com/glorialulu/TSNet
* Documentation: https://tomjanus.github.io/TSNetPlus

Overview
--------

A number of commercial software for transient simulation in water
distribution systems are available in the market; however, the use of
these software for research purposes is limited. The major restriction is
due to the fact that the programs are packed as black boxes, and the source
code is not visible, thus prohibiting any changes, including modification of
existing and implementation of new elements, in the source code.
Therefore, the authors find it imperative to develop an open source package
rendering easiness for interaction, modification, and extension.

Features
--------

TSNetPlus is a Python package designed to perform transient simulation in water
distribution networks. The software includes capabilities to:

* Create water network models based on .inp files
* Generate transient events by operating valves and pumps
* Add disruptive events including pipe bursts and leakages
* Add surge protection devices
* Choose between steady, quasi-steady, and unsteady friction models
* Perform transient simulation using MOC method
* Select the simulation kernel (pure Python or Numba)
* Visualize results

Differences from TSNet
----------------------

* The package is named ``tsnetplus``; ``import tsnet`` becomes
  ``import tsnetplus``. This is a breaking change.
* The simulation kernels are selected with
  ``tsnetplus.backends.ComputeBackend``:

  * ``PYTHON`` - optimised pure-Python kernel (default),
  * ``NUMBA`` - Numba just-in-time compiled kernel (requires ``numba``),
  * ``ORIGINAL`` - the unmodified upstream kernel, kept as a reference
    implementation.

* The benchmarking suite ``benchmarks/benchmark_backends.py`` compares the
  backends in terms of execution time and numerical agreement.

Performance
-----------

On the four benchmark networks shipped with the package, the Numba kernel
reduces the wall-clock time of a transient simulation by between **1.1x and
13x** (median of three timed runs, 120 s simulation on Tnet0: 11.24 s with the
upstream kernel, 0.86 s with the Numba kernel). The optimised pure-Python
kernel gives a further marginal improvement of about 5-10% over the upstream
kernel. The measured pressure head deviates from the upstream kernel by at
most 0.04 m on heads of several hundred metres (about 1e-4 relatively); the
deviations are tabulated in the documentation.

The methodology, the full measured table and the exact environment are
documented in ``docs/performance.rst``.

Installation
------------

From the repository::

    pip install .

With the optional Numba kernel::

    pip install ".[speedups]"

Version
-------

The current version is 0.4.0, the first release of TSNetPlus. It is still a
pre-release.

Contact
-------

* Tomasz Janus, the University of Manchester, tomasz.janus@manchester.ac.uk
* Hector Duque, De Montfort University, hector.j.castro@gmail.com

The authors of the upstream TSNet package, which TSNetPlus is based on, are:

* Lu Xing, the University of Texas at Austin, xinglu@utexas.edu
* Lina Sela, the University of Texas at Austin, linasela@utexas.edu

Disclaimer
----------

No warranty, expressed or implied, is made as to the correctness of the
results or the suitability of the application.

Cite TSNet
-----------

TSNetPlus is a fork of TSNet, so the original TSNet paper remains the
reference publication for the transient simulation model implemented here:

Xing, Lu, and Lina Sela. "Transient simulations in water distribution networks:
TSNet python package." Advances in Engineering Software 149 (2020): 102884.

TSNetPlus itself is not covered by a peer-reviewed publication. If you use it,
please cite this repository (version 0.4.0) in addition to the reference above,
and consider reporting any bug or improvement you find upstream.

License
-------

TSNetPlus is released under the MIT license. See the LICENSE file. The
original copyright of TSNet is retained.
