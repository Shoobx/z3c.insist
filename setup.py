###############################################################################
#
# Copyright 2013 by Shoobx, Inc.
#
###############################################################################

import os
import sys
from setuptools import setup, find_packages

PY3 = sys.version_info.major >= 3

INSTALL_REQUIRES = [
    'setuptools',
    'zope.schema',
    'zope.component',
    'zope.lifecycleevent',
    'iso8601',
]

if not PY3:
    INSTALL_REQUIRES += [
        'configparser'
    ]

def read_file(filename):
    return open(os.path.join(os.path.dirname(__file__), filename)).read()

setup(
    name="z3c.insist",
    version='1.5.8.dev0',
    author="Shoobx, Inc.",
    author_email="dev@shoobx.com",
    description="Persistence to ini Files",
    long_description=
    read_file('README.rst') +
    '\n\n' +
    read_file('CHANGES.rst'),
    keywords="configuration dump serialization",
    url='http://pypi.python.org/pypi/z3c.insist',
    license='ZPL 2.1',
    classifiers=[
        'License :: OSI Approved :: Zope Public License',
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Natural Language :: English',
        'Operating System :: OS Independent',
    ],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    namespace_packages=['z3c', ],
    include_package_data=True,
    zip_safe=False,
    extras_require=dict(
        test=[
            'zope.testing',
            'coverage',
            'python-subunit',
            'junitxml',
            'mock',
            'pytz',
            ],
        enforce=[
            'watchdog>=3.0.0, <4.0.0',
            ],
        ),
    install_requires=INSTALL_REQUIRES,
    entry_points={
        'console_scripts': [
            'perftest = z3c.insist.perftest:main',
            'enftest = z3c.insist.enftest:main',
            ],
        }
)
