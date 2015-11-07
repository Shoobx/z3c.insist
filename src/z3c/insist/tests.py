"""insist -- Persistence to ini files

Test fixture.
"""
import doctest
import unittest
import textwrap

import zope.interface
import zope.component
import zope.component.testing

from z3c.insist import insist, testing, interfaces


class INoneTestSchema(zope.interface.Interface):
    test1 = zope.schema.TextLine()
    test2 = zope.schema.TextLine()
    test3 = zope.schema.TextLine()
    test4 = zope.schema.Int()


@zope.interface.implementer(INoneTestSchema)
class NoneTestObject(object):
    def __init__(self):
        self.test1 = '!None'
        self.test2 = None
        self.test3 = u"To infinity! And beyond!"
        self.test4 = None


class IPerson(zope.interface.Interface):
    firstname = zope.schema.TextLine()
    lastname = zope.schema.TextLine()
    salary = zope.schema.Int()
    male = zope.schema.Bool()

class ICompany(zope.interface.Interface):
    name = zope.schema.TextLine()


@zope.interface.implementer(IPerson)
class Person(object):
    def __init__(self, firstname=None, lastname=None, salary=None, male=None):
        self.firstname = firstname
        self.lastname = lastname
        self.salary = salary
        self.male = male

    def  __repr__(self):
        return "<Person %s %s, %s, salary: %s>" % \
            (self.firstname, self.lastname,
             "male" if self.male else "female",
             self.salary)

@zope.interface.implementer(ICompany)
class Company(object):
    def __init__(self, name=None):
        self.name = name

    def  __repr__(self):
        return "<Company %s>" % self.name


class PersonCollectionStore(insist.CollectionConfigurationStore):
    schema = IPerson
    section_prefix = 'person:'
    item_factory = Person


class MixedClassCollectionStore(insist.CollectionConfigurationStore):
    """Collection store that loads and dumps ICompany and IPerson objects into
    the same collection.
    """
    section_prefix = 'item:'

    def item_factory_typed(self, config, section):
        itype = config.get(section, 'type')
        if itype == 'person':
            return Person()
        else:
            assert itype == 'company'
            return Company()


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

def doctest_CollectionConfigStore_dump():
    """
        Collections can be stored semi-automatically

        >>> coll = {
        ...     'jeb': Person("Jebediah", "Kerman", 20000, True),
        ...     'val': Person("Valentina", "Kerman", 30000, False),
        ... }
        >>> itemstore = lambda ctx: insist.ConfigurationStore.makeStore(
        ...     ctx, IPerson, 'test')
        >>> gsm = zope.component.getGlobalSiteManager()
        >>> gsm.registerAdapter(itemstore, (IPerson, ), interfaces.IConfigurationStore, '')

        >>> store = PersonCollectionStore(coll)
        >>> print store.dumps()
        [person:jeb]
        firstname = Jebediah
        lastname = Kerman
        salary = 20000
        male = True
        <BLANKLINE>
        [person:val]
        firstname = Valentina
        lastname = Kerman
        salary = 30000
        male = False
    """

def doctest_CollectionConfigStore_load_fresh():
    """ Load completely new collection

        >>> ini = textwrap.dedent('''
        ... [person:jeb]
        ... firstname = Jebediah
        ... lastname = Kerman
        ... salary = 20000
        ... male = True
        ...
        ... [person:val]
        ... firstname = Valentina
        ... lastname = Kerman
        ... salary = 30000
        ... male = False
        ... ''')

        >>> itemstore = lambda ctx: insist.ConfigurationStore.makeStore(
        ...     ctx, IPerson, 'test')
        >>> gsm = zope.component.getGlobalSiteManager()
        >>> gsm.registerAdapter(itemstore, (IPerson, ), interfaces.IConfigurationStore, '')

        >>> coll = {}
        >>> store = PersonCollectionStore(coll)
        >>> store.loads(ini)

        >>> coll
        {'jeb': <Person Jebediah Kerman, male, salary: 20000>,
         'val': <Person Valentina Kerman, female, salary: 30000>}
    """

def doctest_CollectionConfigStore_load_changeaddremove():
    """ Add one item and remove another

    Load initial collection
        >>> ini = textwrap.dedent('''
        ... [person:jeb]
        ... firstname = Jebediah
        ... lastname = Kerman
        ... salary = 20000
        ... male = True
        ...
        ... [person:val]
        ... firstname = Valentina
        ... lastname = Kerman
        ... salary = 30000
        ... male = False
        ... ''')

        >>> itemstore = lambda ctx: insist.ConfigurationStore.makeStore(
        ...     ctx, IPerson, 'test')
        >>> gsm = zope.component.getGlobalSiteManager()
        >>> gsm.registerAdapter(itemstore, (IPerson, ), interfaces.IConfigurationStore, '')

        >>> coll = {}
        >>> store = PersonCollectionStore(coll)
        >>> store.loads(ini)

        >>> coll
        {'jeb': <Person Jebediah Kerman, male, salary: 20000>,
         'val': <Person Valentina Kerman, female, salary: 30000>}

    Save loaded items for future reference

        >>> jeb = coll['jeb']
        >>> val = coll['val']

    Now let's change the configuration - remove one item and add another

        >>> ini = textwrap.dedent('''
        ... [person:bill]
        ... firstname = Bill
        ... lastname = Kerman
        ... salary = 30000
        ... male = True
        ...
        ... [person:val]
        ... firstname = Valentina
        ... lastname = Kerman
        ... salary = 30000
        ... male = False
        ... ''')

        >>> store.loads(ini)
        >>> coll
        {'bill': <Person Bill Kerman, male, salary: 30000>,
         'val': <Person Valentina Kerman, female, salary: 30000>}

        >>> bill = coll['bill']

    Make sure we didn't just edit "jeb", but created new item. Also, `val`
    should stay unchanged.

        >>> jeb is coll['bill']
        False

        >>> val is coll['val']
        True

    Now, change the salary of a bill, and remove val

        >>> ini = textwrap.dedent('''
        ... [person:bill]
        ... firstname = Bill
        ... lastname = Kerman
        ... salary = 50000
        ... male = True
        ... ''')

        >>> store.loads(ini)
        >>> coll
        {'bill': <Person Bill Kerman, male, salary: 50000>}

    Bill should not change his identity by this operation

        >>> bill is coll['bill']
        True
    """

def doctest_CollectionConfigStore_load_typed():
    """ Test collections with items of different types

    First, register adapters
        >>> gsm = zope.component.getGlobalSiteManager()

        >>> personstore = lambda ctx: insist.ConfigurationStore.makeStore(
        ...     ctx, IPerson, 'person')
        >>> gsm.registerAdapter(personstore, (IPerson, ),
        ...                     interfaces.IConfigurationStore, '')

        >>> companystore = lambda ctx: insist.ConfigurationStore.makeStore(
        ...     ctx, ICompany, 'company')
        >>> gsm.registerAdapter(companystore, (ICompany, ),
        ...                     interfaces.IConfigurationStore, '')

        >>> coll = {}
        >>> store = MixedClassCollectionStore(coll)

    Load initial data
        >>> ini = textwrap.dedent('''
        ... [item:jeb]
        ... type = person
        ... firstname = Jebediah
        ... lastname = Kerman
        ... salary = 20000
        ... male = True
        ...
        ... [item:pp]
        ... type = company
        ... name = Pied Piper, Inc
        ... ''')

        >>> store.loads(ini)

        >>> coll
        {'jeb': <Person Jebediah Kerman, male, salary: 20000>,
         'pp': <Company Pied Piper, Inc>}

    Now, suddenly, jeb becomes a company

        >>> ini = textwrap.dedent('''
        ... [item:jeb]
        ... type = company
        ... name = Jeb Startup, Inc
        ...
        ... [item:pp]
        ... type = company
        ... name = Pied Piper, Inc
        ... ''')

        >>> store.loads(ini)
        >>> coll
        {'jeb': <Company Jeb Startup, Inc>,
         'pp': <Company Pied Piper, Inc>}

    """


def doctest_ListFieldSerializer_edge_cases():
    r"""
    Tuple and list fields are serialized as multiline values.

    Check that None gets serialized and can be read back

        >>> class INumbers(zope.interface.Interface):
        ...     numbers = zope.schema.List(
        ...         value_type=zope.schema.Int())

        >>> class Numbers(object):
        ...     numbers = None

        >>> nums = Numbers()
        >>> nums.numbers = [42, None]
        >>> store = insist.ConfigurationStore.makeStore(nums, INumbers, 'numbers')
        >>> print store.dumps()
        [numbers]
        numbers = 42, !!None

    Well it gets double escaped...
    But it won't fail loading

        >>> store.loads('''\
        ... [numbers]
        ... numbers = 42, !!None
        ... ''')
        >>> nums.numbers
        [42, None]

        >>> store.loads('''\
        ... [numbers]
        ... numbers =
        ... ''')
        >>> nums.numbers
        []

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
