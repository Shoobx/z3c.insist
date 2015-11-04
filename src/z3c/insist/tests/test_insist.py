###############################################################################
#
# Copyright 2013-15 by Shoobx, Inc.
#
###############################################################################
"""insist -- Persistence to ini files

Test fixture.
"""
import collections
import doctest
import os
import unittest
import textwrap

import zope.interface
import zope.component
import zope.component.testing

from z3c.insist import insist, interfaces, testing


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


class ISimple(zope.interface.Interface):
    text = zope.schema.Text()


class Simple(object):
    zope.interface.implements(ISimple)
    def __init__(self, text=None):
        self.text = text
    def __repr__(self):
        return 'Simple(%r)' % self.text


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

def doctest_ConfigurationStore_file_header():
    """The configurations tore can also place a file header on top of the file.

       >>> obj = NoneTestObject()
       >>> store = insist.ConfigurationStore.makeStore(
       ...     obj, INoneTestSchema, 'test')
       >>> store.file_header = '# Nice file header\\n'

    Nones and bangs get escaped:

       >>> print store.dumps()
       # Nice file header
       <BLANKLINE>
       [test]
       test1 = !!None
       test2 = !None
       test3 = To infinity!! And beyond!!
       test4 = !None

    """

def doctest_CollectionConfigurationStore():
    """Collection Configuration Store Tests

    This configuration store orchestrates storage of collections/mappings. To
    make the collection store usable a few attributes and methods must be
    provided:

       >>> class SimpleCollectionStore(insist.CollectionConfigurationStore):
       ...     schema = ISimple
       ...     section_prefix = 'simple:'
       ...     item_factory = Simple

    We also have to register a store for the object itself:

       >>> @zope.component.adapter(ISimple)
       ... @zope.interface.implementer(interfaces.IConfigurationStore)
       ... class SimpleStore(insist.ConfigurationStore):
       ...     schema = ISimple

       >>> reg = zope.component.provideAdapter(SimpleStore)

    Now, let's create a simple collection and create a store for it:

       >>> coll = collections.OrderedDict([
       ...     ('one', Simple(u'Number 1')),
       ...     ('two', Simple(u'Two is a charm')),
       ...     ('three', Simple(u'The tail.'))
       ...     ])

       >>> store = SimpleCollectionStore(coll)

    Let's have a look at the dump:

       >>> print store.dumps()
       [simple:one]
       text = Number 1
       <BLANKLINE>
       [simple:two]
       text = Two is a charm
       <BLANKLINE>
       [simple:three]
       text = The tail.

    Now let's test the roundtrip:

       >>> coll2 = {}
       >>> store2 = SimpleCollectionStore(coll2)
       >>> store2.loads(store.dumps())

       >>> import pprint
       >>> pprint.pprint(coll2)
       {'one': Simple(u'Number 1'),
        'three': Simple(u'The tail.'),
        'two': Simple(u'Two is a charm')}

    """


def doctest_SeparateFileConfigurationStore():
    """Separate File Configuration Store Test

    As the name suggests, this store allows its configuration to be stored in
    a separate file. For this store to work, we need to implement a method
    that tells the store where to store the file:

       >>> import tempfile
       >>> dir = tempfile.mkdtemp()

       >>> class NoneTestStore(insist.SeparateFileConfigurationStore):
       ...     def getConfigPath(self):
       ...         return dir

    Let's now dump our data:

       >>> obj = NoneTestObject()
       >>> store = NoneTestStore.makeStore(obj, INoneTestSchema, 'test')

    As we can see, a small stub of the configuration si written to the
    original store.

       >>> print store.dumps()
       [test]
       config-file = test.ini

    But the actual data is in the new file, which is named by default like the
    section:

       >>> with open(os.path.join(dir, 'test.ini')) as file:
       ...     print file.read()
       [test]
       test1 = !!None
       test2 = !None
       test3 = To infinity!! And beyond!!
       test4 = !None

    Let's now load the data again:

       >>> obj2 = NoneTestObject()
       >>> obj2.test1 = obj2.test2 = obj2.test3 = u'Test'
       >>> obj2.test4 = 5
       >>> store2 = NoneTestStore.makeStore(obj2, INoneTestSchema, 'test')

       >>> store2.loads(store.dumps())
       >>> obj2.test1
       u'!None'
       >>> obj2.test2
       >>> obj2.test3
       u'To infinity! And beyond!'
       >>> obj2.test4

    We can also tell the store not to leave the stub in the main config
    file. That requires extra code though to ensure that all config files are
    loaded.

       >>> store.dumpSectionStub = False
       >>> print store.dumps()
       <BLANKLINE>

    Finally, in order to ease migration from monolithic configuration files to
    split files, the store reads the main configuration if it cannot find the
    file.

       >>> os.remove(os.path.join(dir, 'test.ini'))
       >>> os.listdir(dir)
       []

       >>> obj3 = NoneTestObject()
       >>> obj3.test1 = obj3.test2 = obj3.test3 = u'Test'
       >>> store3 = NoneTestStore.makeStore(obj3, INoneTestSchema, 'test')

       >>> store3.loads('''
       ... [test]
       ... test1 = !!None
       ... test2 = !None
       ... test3 = To infinity!! And beyond!!
       ... test4 = !None
       ... ''')
       >>> obj3.test1
       u'!None'
       >>> obj3.test2
       >>> obj3.test3
       u'To infinity! And beyond!'
       >>> obj3.test4
    """

def doctest_SeparateFileCollectionConfigurationStore():
    """Separate File Collection Configuration Store Test

    This class is very similar to the regular colelction store except that all
    items are stored in a separate file. So let's do the setup:

       >>> import tempfile
       >>> dir = tempfile.mkdtemp()

       >>> class SimpleCollectionStore(
       ...         insist.SeparateFileCollectionConfigurationStore):
       ...
       ...     section = 'simple-collection'
       ...     schema = ISimple
       ...     section_prefix = 'simple:'
       ...     item_factory = Simple
       ...
       ...     def getConfigPath(self):
       ...         return dir

       >>> @zope.component.adapter(ISimple)
       ... @zope.interface.implementer(interfaces.IConfigurationStore)
       ... class SimpleStore(insist.ConfigurationStore):
       ...     schema = ISimple

       >>> reg = zope.component.provideAdapter(SimpleStore)

    Now, let's create a simple collection and create a store for it:

       >>> coll = collections.OrderedDict([
       ...     ('one', Simple(u'Number 1')),
       ...     ('two', Simple(u'Two is a charm')),
       ...     ('three', Simple(u'The tail.'))
       ...     ])

       >>> store = SimpleCollectionStore(coll)

    Let's have a look at the dump:

       >>> print store.dumps()
       [simple-collection]
       config-file = simple-collection.ini

       >>> with open(os.path.join(dir, 'simple-collection.ini')) as file:
       ...     print file.read()
       [simple:one]
       text = Number 1
       <BLANKLINE>
       [simple:two]
       text = Two is a charm
       <BLANKLINE>
       [simple:three]
       text = The tail.


    Let's now ensure that we can load the data again:

       >>> coll2 = {}
       >>> store2 = SimpleCollectionStore(coll2)
       >>> store2.loads(store.dumps())

       >>> import pprint
       >>> pprint.pprint(coll2)
       {'one': Simple(u'Number 1'),
        'three': Simple(u'The tail.'),
        'two': Simple(u'Two is a charm')}

    """

def doctest_FileSectionsCollectionConfigurationStore():
    """File Section Configuration Store Test

    If you do not want to store a stub of a section in the main config file,
    you have to provide the collection config store with the ability to
    discover configuration files and only select the correct ones.

    Let's setup a collection store with its file object store that does not
    dump the stub.

       >>> import tempfile
       >>> dir = tempfile.mkdtemp()

       >>> class SimpleCollectionStore(
       ...         insist.FileSectionsCollectionConfigurationStore):
       ...
       ...     schema = ISimple
       ...     section_prefix = 'simple:'
       ...     item_factory = Simple
       ...
       ...     def getConfigPath(self):
       ...         return dir

       >>> @zope.component.adapter(ISimple)
       ... @zope.interface.implementer_only(interfaces.IConfigurationStore)
       ... class SimpleStore(insist.SeparateFileConfigurationStore):
       ...     dumpSectionStub = False
       ...     schema = ISimple
       ...
       ...     def getConfigPath(self):
       ...         return dir

       >>> reg = zope.component.provideAdapter(SimpleStore)

    Okay, now things are getting exciting. Let's dump a collection and see
    what happens:

       >>> coll = collections.OrderedDict([
       ...     ('one', Simple(u'Number 1')),
       ...     ('two', Simple(u'Two is a charm')),
       ...     ('three', Simple(u'The tail.'))
       ...     ])

       >>> store = SimpleCollectionStore(coll)
       >>> print store.dumps()
       <BLANKLINE>

       >>> for fn in sorted(os.listdir(dir)):
       ...     if not fn.startswith(store.section_prefix):
       ...         continue
       ...     with open(os.path.join(dir, fn)) as file:
       ...         print '---', fn, '---'
       ...         print file.read()
       --- simple:one.ini ---
       [simple:one]
       text = Number 1
       <BLANKLINE>
       --- simple:three.ini ---
       [simple:three]
       text = The tail.
       <BLANKLINE>
       --- simple:two.ini ---
       [simple:two]
       text = Two is a charm

    Now the more interesting part, loading everything again:

       >>> coll2 = {}
       >>> store2 = SimpleCollectionStore(coll2)
       >>> store2.loads(store.dumps())

       >>> import pprint
       >>> pprint.pprint(coll2)
       {'one': Simple(u'Number 1'),
        'three': Simple(u'The tail.'),
        'two': Simple(u'Two is a charm')}
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
        '../insist.txt',
        setUp=setUp, tearDown=tearDown, optionflags=optionflags)
    tests = doctest.DocTestSuite(
        setUp=setUp, tearDown=tearDown, optionflags=optionflags)

    return unittest.TestSuite([files, tests])
