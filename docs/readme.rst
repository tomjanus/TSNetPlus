Introduction to TSNetPlus
=========================
TSNetPlus performs transient simulation in water networks using Method of
Characteristics (MOC). It is a fork of `TSNet
<https://github.com/glorialulu/TSNet>`_ whose main purpose is to make the
transient simulation faster; see :doc:`fork` and :doc:`performance`.

On the benchmark networks shipped with the package, the Numba kernel runs a
transient simulation between 1.1x and 13x faster than the upstream kernel,
while staying within about ``1e-4`` (relative) of the upstream results. The
measured times and deviations are tabulated in :doc:`performance`.

* Free software: MIT license
* Github: https://github.com/tomjanus/TSNetPlus.git
* Upstream project: https://github.com/glorialulu/TSNet

Overview
---------
Hydraulic transients in water distribution networks (WDNs),
typically induced by pipe bursts, valve operations, and pump operations,
can disturb the steady-state flow conditions by introducing extreme pressure
variability and imposing abrupt internal pressure force
onto the pipeline systems [WOLB05]_.
These disturbances have been identified as one of the major contributing factors
in the many pipe deterioration and catastrophic failure in WDNs [RERS15]_,
thereby wasting a significant amount of treated water and creating unexpected
possibilities of contamination intrusion [ASCE17]_.
Consequently, transient simulation, as a prominent approach to
understand and predict the behavior of hydraulic transients,
has become an essential requirement for ensuring the distribution safety and
improving the efficiency in the process of design and operation of WDNs.
In addition to improving design and operation of WDNs,
various other transient-based applications, such as network calibration,
leak detection, sensor placement, and condition assessment,
has also enhanced the popularity and necessity of transient simulation

Acknowledgedly, a number of commercial software for transient simulation
in water distribution systems is available in the market;
however, the use of these software for research purposes is limited.
The major restriction is due to the fact that the programs are packed
as black boxes, and the source codes are not visible,
thus prohibiting any changes, including modification of
existing and implementation of new elements, in the source codes.
Additionally, the commercial software is designed to perform only
single transient simulations and do not have the capabilities to automate or
run multiple transient simulations.
Users are required to modify the boundary conditions using the GUI,
perform the simulation, and manually record the hydraulic responses
in the various conditions,
which significantly complicated the research process.

There is a clear gap that currently available simulation software
are not suitable for many research applications beyond the
conventional design purposes.
Hence, the motivation of this work is two-fold:

1.  Provide users with open source and freely available python code
and package for simulating transients in water distribution systems
that can be integrated with other case specific applications,
e.g. sensor placement and event detection; and

2.  Encourage users and developers to further develop and
extend the transient model.


Features
--------

TSNetPlus is a Python package designed to perform transient simulation in water
distribution networks. The software includes capability to:

* Create transient models based on EPANET INP files
* Operating valves and pumps
* Add disruptive events including pipe bursts and leakages
* Choose between steady,quasi-steady, and unsteady friction models
* Perform transient simulation using Method of characteristics (MOC) techniques
* Choose the simulation kernel (pure Python or Numba) to trade speed for
  numerical precision
* Visualize results

For more information, see the rest of this documentation.


Version
-------

The current version of TSNetPlus is 0.4.0, the first release of the fork, which
is still a pre-release.

Contact
-------

* Tomasz Janus, the University of Manchester, tomasz.janus@manchester.ac.uk
* Hector Duque, De Montfort University

The authors of the upstream TSNet package are:

* Lu Xing, the University of Texas at Austin, xinglu@utexas.edu
* Lina Sela, the University of Texas at Austin, linasela@utexas.edu

Disclaimer
----------

No warranty, expressed or implied, is made as to the correctness of the
results or the suitability of the application.


Cite TSNet
-----------

To cite the transient simulation model implemented in TSNetPlus, use the
reference of the upstream package:

Xing, Lu, and Lina Sela. "Transient simulations in water distribution networks:
TSNet python package." Advances in Engineering Software 149 (2020): 102884.

TSNetPlus itself is not covered by a peer-reviewed publication; please cite
this repository in addition to the reference above.


License
-------

TSNetPlus is released under the MIT license. See the LICENSE file. The
original copyright of TSNet is retained.
