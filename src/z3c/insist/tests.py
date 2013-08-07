"""insist -- Persistence to ini files

Test fixture.
"""
import doctest

import zope.component
import zope.component.testing

from z3c.insist import insist


def setUp(test):
    zope.component.testing.setUp(test)
    zope.component.provideAdapter(insist.TextFieldSerializer)
    zope.component.provideAdapter(insist.IntFieldSerializer)


def tearDown(test):
    zope.component.testing.tearDown(test)


def test_suite():
    return doctest.DocFileSuite('insist.txt',
                                setUp=setUp, tearDown=tearDown,
                                optionflags=(doctest.NORMALIZE_WHITESPACE|
                                             doctest.REPORT_NDIFF|
                                             doctest.ELLIPSIS))
