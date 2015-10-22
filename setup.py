###############################################################################
#
# Copyright 2013 by Shoobx, Inc.
#
###############################################################################
import os
from setuptools import setup, find_packages


def read_file(filename):
    return open(os.path.join(os.path.dirname(__file__), filename)).read()

setup(
    name="z3c.insist",
    version='0.1.0dev7',
    author="Shoobx, Inc.",
    author_email="dev@shoobx.com",
    description="Persistence to ini files",
    long_description=
    read_file('README.rst') +
    '\n\n' +
    read_file('CHANGES.rst'),
    keywords="configuration dump serialization",
    license='Proprietary',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Natural Language :: English',
        'Operating System :: OS Independent',
    ],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    namespace_packages=['z3c', ],
    include_package_data=True,
    zip_safe=False,
    extras_require=dict(
        test=['zope.testing',
              'coverage',
              'python-subunit',
              'junitxml',
              'pytz',
              ],),
    install_requires=[
        'setuptools',
        'zope.schema',
        'zope.component',
        'zope.lifecycleevent',
        'iso8601',
    ]
)
