"""insist -- Persistence to ini files

Test fixture.
"""
import doctest
import unittest

import zope.component
import zope.component.testing

from z3c.insist import insist, testing


class INoneTestSchema(zope.interface.Interface):
    test1 = zope.schema.TextLine()
    test2 = zope.schema.TextLine()
    test3 = zope.schema.TextLine()
    test4 = zope.schema.Int()


class NoneTestObject(object):
    def __init__(self):
        self.test1 = '!None'
        self.test2 = None
        self.test3 = u"To infinity! And beyond!"
        self.test4 = None


def doctest_FieldSerializer_None():
    """Test escaping of None values and handling of the escape character

       >>> obj = NoneTestObject()
       >>> store = insist.ConfigurationStore.makeStore(
       ...     obj, INoneTestSchema, 'test')

    Nones and bangs get escaped:

       >>> print store.dumps()
       [test]
       test1 = !!None
       test2 = !None
       test3 = To infinity!! And beyond!!
       test4 = !None

    Now let's test the roundtrip:

       >>> store.loads(store.dumps())

       >>> obj.test1
       u'!None'
       >>> obj.test2
       >>> obj.test3
       u'To infinity! And beyond!'
       >>> obj.test4

    """

def doctest_ConfigurationStore_load_missing_values():
    r"""Test that missing configuration values are handled fine.

       >>> obj = NoneTestObject()
       >>> store = insist.ConfigurationStore.makeStore(
       ...     obj, INoneTestSchema, 'test')

       >>> store.loads('''\
       ... [test]
       ... test1 = foo
       ... ''')

       >>> obj.test1
       u'foo'
       >>> obj.test2
       >>> obj.test3
       u'To infinity! And beyond!'
       >>> obj.test4

    """


def doctest_ConfigurationStore_section():
    """The section name defaults to the interface name.

       >>> obj = NoneTestObject()
       >>> store = insist.ConfigurationStore(obj)
       >>> store.schema = INoneTestSchema

       >>> store.section
       'INoneTestSchema'

       >>> store.section = 'specific'
       >>> store.section
       'specific'

    """


def setUp(test):
    zope.component.testing.setUp(test)
    testing.setUpSerializers()


def tearDown(test):
    zope.component.testing.tearDown(test)


def test_suite():
    optionflags=(doctest.NORMALIZE_WHITESPACE|
                 doctest.REPORT_NDIFF|
                 doctest.ELLIPSIS)
    files = doctest.DocFileSuite(
        'insist.txt', setUp=setUp, tearDown=tearDown, optionflags=optionflags)
    tests = doctest.DocTestSuite(
        setUp=setUp, tearDown=tearDown, optionflags=optionflags)

    return unittest.TestSuite([files, tests])
