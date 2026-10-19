#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
                'pandas',
                'numpy',
                'scipy',
                'matplotlib',
                'plotly',
                'wntr',
                'networkx',
                ]

# Optional dependency enabling the Numba just-in-time compiled kernel.
speedups_requirements = ['numba', ]

setup_requirements = ['pytest-runner', ]

test_requirements = ['pytest', ]

setup(
    author="Tomasz Janus and Hector Duque",
    author_email='tomasz.janus@manchester.ac.uk',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    description=(
        "TSNetPlus is a fork of TSNet that conducts transient simulation "
        "using the MOC method for water distribution systems, with "
        "significantly faster simulation kernels."
    ),
    entry_points={},
    install_requires=requirements,
    extras_require={'speedups': speedups_requirements},
    license="MIT license",
    python_requires='>=3.10',
    long_description=readme + '\n\n' + history,
    long_description_content_type='text/x-rst',
    include_package_data=True,
    keywords='tsnetplus, tsnet, water distribution networks, transient simulation, MOC, numba',
    name='tsnetplus',
    packages=['tsnetplus'],
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/tomjanus/TSNetPlus',
    version='0.4.0',
    zip_safe=False,
)
