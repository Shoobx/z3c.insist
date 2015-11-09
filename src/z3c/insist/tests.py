"""insist -- Persistence to ini files

Test fixture.
"""
import datetime
import doctest
import unittest
import textwrap
from collections import OrderedDict

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


    Check what happens when there's a separator in an item

        >>> class ISomeTexts(zope.interface.Interface):
        ...     sometexts = zope.schema.List(
        ...         value_type=zope.schema.TextLine())

        >>> class SomeTexts(object):
        ...     sometexts = None

        >>> texts = SomeTexts()
        >>> texts.sometexts = [u'42', None, u', ', u'foo']
        >>> store = insist.ConfigurationStore.makeStore(
        ...     texts, ISomeTexts, 'sometexts')
        >>> print store.dumps()
        [sometexts]
        sometexts = 42, !!None, , , foo

        >>> store.loads('''\
        ... [sometexts]
        ... sometexts = 42, !!None, , , foo
        ... ''')

    oooooooooops, that u', ' we sent in is gone...
    don't try this at home

        >>> texts.sometexts
        [u'42', None, u'', u'', u'foo']


    Let's see what happens is value_type is List

        >>> class IPerson(zope.interface.Interface):
        ...     somedata = zope.schema.List(
        ...         value_type=zope.schema.Dict(
        ...             key_type=zope.schema.TextLine(),
        ...             value_type=zope.schema.TextLine()))

        >>> class Person(object):
        ...     somedata = None

        >>> p = Person()
        >>> store = insist.ConfigurationStore.makeStore(p, IPerson, 'person')

        >>> p.somedata = [
        ...     {u'first': u'foo'}, {u'second': u'bar', u'third': u'fun'}]
        >>> print store.dumps()
        [person]
        somedata = first::foo, second::bar
            third::fun

        >>> store.loads(store.dumps())
        >>> p.somedata
        [{u'first': u'foo'}, {u'second': u'bar', u'third': u'fun'}]

    """


def doctest_DictFieldSerializer_edge_cases():
    r"""
    Dict fields get JSONified.

    Check what happens with None

        >>> class IPerson(zope.interface.Interface):
        ...     somedata = zope.schema.Dict(
        ...         key_type=zope.schema.TextLine(),
        ...         value_type=zope.schema.Int())

        >>> class Person(object):
        ...     somedata = None

        >>> p = Person()
        >>> store = insist.ConfigurationStore.makeStore(p, IPerson, 'person')

        >>> p.somedata = None
        >>> print store.dumps()
        [person]
        somedata = !None

        >>> p.somedata = OrderedDict([
        ...     (u'foo', 42),
        ...     (u'bar', None)])
        >>> print store.dumps()
        [person]
        somedata = foo::42
            bar::!!None

        >>> store.loads('''\
        ... [person]
        ... somedata = !None
        ... ''')
        >>> p.somedata is None
        True

        >>> store.loads('''\
        ... [person]
        ... somedata =
        ... ''')
        >>> p.somedata
        {}

    None in value_type:

        >>> store.loads('''\
        ... [person]
        ... somedata = bar::15
        ...     foo::!!None
        ... ''')
        >>> sorted(p.somedata.items())
        [(u'bar', 15), (u'foo', None)]

    Some weirdos:

        >>> store.loads('''\
        ... [person]
        ... somedata = {}
        ... ''')
        Traceback (most recent call last):
        ...
        ValueError: need more than 1 value to unpack

        >>> store.loads('''\
        ... [person]
        ... somedata = ::
        ... ''')
        Traceback (most recent call last):
        ...
        ValueError: invalid literal for int() with base 10: ''

        >>> store.loads('''\
        ... [person]
        ... somedata = ::42
        ... ''')
        >>> p.somedata
        {u'': 42}

        >>> store.loads('''\
        ... [person]
        ... somedata =
        ...     bar::42
        ... ''')
        >>> p.somedata
        {u'bar': 42}

    Separator in key_type or value_type fails
    Choose your separator wisely

        >>> store.loads('''\
        ... [person]
        ... somedata =
        ...     ba::r::42
        ... ''')
        Traceback (most recent call last):
        ...
        ValueError: invalid literal for int() with base 10: 'r::42'

    OrderedDict as factory:

        >>> save_factory = insist.DictFieldSerializer.factory
        >>> insist.DictFieldSerializer.factory = OrderedDict

        >>> store.loads('''\
        ... [person]
        ... somedata = bar::42
        ...     foo::666
        ... ''')

        >>> p.somedata
        OrderedDict([(u'bar', 42), (u'foo', 666)])

        >>> store.loads('''\
        ... [person]
        ... somedata = foo::402
        ...     bar::987
        ... ''')

        >>> p.somedata
        OrderedDict([(u'foo', 402), (u'bar', 987)])

        >>> insist.DictFieldSerializer.factory = save_factory

    Date as value_type:

        >>> class IPerson(zope.interface.Interface):
        ...     somedata = zope.schema.Dict(
        ...         key_type=zope.schema.TextLine(),
        ...         value_type=zope.schema.Date())

        >>> class Person(object):
        ...     somedata = None

        >>> p = Person()
        >>> store = insist.ConfigurationStore.makeStore(p, IPerson, 'person')

        >>> p.somedata = {u'foo': datetime.date(2015, 11, 7), u'bar': None}
        >>> print store.dumps()
        [person]
        somedata = foo::2015-11-07
            bar::!!None

        >>> store.loads('''\
        ... [person]
        ... somedata = !None
        ... ''')
        >>> p.somedata is None
        True

        >>> store.loads('''\
        ... [person]
        ... somedata =
        ... ''')
        >>> p.somedata
        {}

        >>> store.loads('''\
        ... [person]
        ... somedata = foo::2015-11-07
        ...     bar::!!None
        ... ''')
        >>> sorted(p.somedata.items())
        [(u'bar', None), (u'foo', datetime.date(2015, 11, 7))]

    What happens when value_type does not conform?

        >>> store.loads('''\
        ... [person]
        ... somedata = foo::42
        ...     bar::!!None
        ... ''')
        Traceback (most recent call last):
        ...
        ValueError: time data '42' does not match format '%Y-%m-%d'

    Let's see that unicode strings survive dump and load

        >>> p.somedata = {u'foo\u07d0': None}
        >>> store.loads(store.dumps())
        >>> p.somedata
        {u'foo\u07d0': None}

    Let's see that \n and friends survive load and dump

        >>> class IPerson(zope.interface.Interface):
        ...     somedata = zope.schema.Dict(
        ...         key_type=zope.schema.TextLine(),
        ...         value_type=zope.schema.Text())

        >>> class Person(object):
        ...     somedata = None

        >>> p = Person()
        >>> store = insist.ConfigurationStore.makeStore(p, IPerson, 'person')

        >>> p.somedata = {u'foo': 'first\nsecond\rthird\ta tab'}
        >>> print store.dumps()
        [person]
        somedata = foo::first\nsecond\rthird\ta tab

        >>> store.loads(store.dumps())
        >>> p.somedata
        {u'foo': u'first\nsecond\rthird\ta tab'}

    Let's see what happens is value_type is List

        >>> class IPerson(zope.interface.Interface):
        ...     somedata = zope.schema.Dict(
        ...         key_type=zope.schema.TextLine(),
        ...         value_type=zope.schema.List(
        ...             value_type=zope.schema.TextLine()))

        >>> class Person(object):
        ...     somedata = None

        >>> p = Person()
        >>> store = insist.ConfigurationStore.makeStore(p, IPerson, 'person')

        >>> p.somedata = {u'foo': [u'first', u'second']}
        >>> print store.dumps()
        [person]
        somedata = foo::first, second

        >>> store.loads(store.dumps())
        >>> p.somedata
        {u'foo': [u'first', u'second']}

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
