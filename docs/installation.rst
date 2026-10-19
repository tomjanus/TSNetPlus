.. highlight:: shell

============
Installation
============

Setup Python Environment
------------------------------

TSNetPlus is tested against Python versions 3.12, 3.13, and 3.14.
It can be installed on Windows, Linux, and Mac OS X operating systems.
Python distributions, such as Anaconda, are recommended to manage the Python
environment as they already contain (or easily support installation of) many
Python packages (e.g. SciPy, NumPy, pandas, pip, matplotlib, etc.) that are
used in the TSNetPlus package.  For more information on Python package
dependencies, see :ref:`Dependencies`.

Stable Release (for users)
--------------------------

To install TSNetPlus from the sources, run this command in your terminal:

.. code-block:: console

    $ pip install tsnetplus

TSNetPlus is not published on PyPI at the time of writing. The command above
therefore only works from a checkout of the repository.

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From Sources (for developers)
-----------------------------

The sources for TSNetPlus can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone https://github.com/tomjanus/TSNetPlus.git

Or download the `tarball`_:

.. code-block:: console

    $ curl  -OL https://github.com/tomjanus/TSNetPlus/tarball/master

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ pip install .

The Numba kernel is an optional dependency and is installed with the
``speedups`` extra:

.. code-block:: console

    $ pip install ".[speedups]"


.. _Github repo: https://github.com/tomjanus/TSNetPlus
.. _tarball: https://github.com/tomjanus/TSNetPlus/tarball/master

.. _Dependencies:

Dependencies
------------

Requirements for TSNetPlus include Python (3.12, 3.13, or 3.14) along with
several Python packages.
The following Python packages are required:

1.  Numpy [VaCV11]_: the fundamental package needed for scientific computing with Python
    included in Anaconda distribution
    http://www.numpy.org/

2.  Matplotlib [Hunt07]_: Python 2D plotting library
    included in Anaconda distribution
    http://matplotlib.org/

3.  NetworkX [HaSS08]_: Network creation and manipulation engine,
    install on a python-enabled command line with `pip install wntr`
    https://networkx.github.io/

4.  WNTR [WNTRSi]_: Water Network Tool for Resilience
    install on a python-enabled command line with `pip install wntr`
    http://wntr.readthedocs.io
    WNTR does not publish pre-compiled wheels for Python 3.14, so on that
    version it is built from source and a C++ compiler must be available
    (``CXX=g++`` for example)

5.  pytest: Unit Tests engine
    install on a python-enabled command line with `pip install -U pytest`
    https://docs.pytest.org/en/latest/

6.  rich: Rich text formatting used by the logging configuration
    install on a python-enabled command line with `pip install rich`
    https://rich.readthedocs.io

7.  numba (optional): just-in-time compiler for the fastest simulation kernel
    install on a python-enabled command line with `pip install numba`
    https://numba.pydata.org/

