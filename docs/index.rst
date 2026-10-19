====================================================
TSNetPlus: transient simulation in water networks
====================================================

.. figure:: figures/highlight.png
   :width: 600
   :alt: highlight

TSNetPlus is a Python package that performs transient simulation in water
distribution networks using the Method of Characteristics (MOC). It is a fork
of `TSNet <https://github.com/glorialulu/TSNet>`_ that adds pluggable, faster
simulation kernels. Start with :doc:`readme`, then read :doc:`fork` to see
what changed with respect to TSNet and :doc:`performance` for the measured
speed-up.

The software includes the capability to:

* Create transient models based on EPANET INP files
* Operate valves and pumps
* Add disruptive events including pipe bursts and leaks
* Model open and closed surge tanks
* Choose between steady, quasi-steady, and unsteady friction models
* Perform transient simulation using Method of characteristics (MOC) techniques
* Choose the simulation kernel (pure Python or Numba) to trade speed for
  numerical precision
* Visualize results

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   readme
   fork
   performance
   installation
   limitations
   usage
   transient
   results
   examples
   validation
   contributing
   authors
   history
   API documentation <apidocs/tsnetplus>
   abbrev
   reference
