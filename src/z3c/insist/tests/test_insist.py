###############################################################################
#
# Copyright 2013-15 by Shoobx, Inc.
#
###############################################################################
"""insist -- Persistence to ini files

Test fixture.
"""
from __future__ import print_function

import collections
import datetime
import doctest
import os
import pprint
import textwrap
import unittest
from collections import OrderedDict

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


@zope.interface.implementer(ISimple)
class Simple(object):
    def __init__(self, text=None):
        self.text = text

    def __repr__(self):
        return 'Simple(%r)' % self.text

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.text == other.text


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

    def __eq__(self, other):
        return \
          (self.firstname, self.lastname, self.salary, self.male) == \
          (other.firstname, other.lastname, other.salary, other.male)

@zope.interface.implementer(ICompany)
class Company(object):
    def __init__(self, name=None):
        self.name = name

    def  __repr__(self):
        return "<Company %s>" % self.name

    def __eq__(self, other):
        return self.name == other.name


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


class InsistTest(unittest.TestCase):

    def setUp(self):
        zope.component.testing.setUp(self)
        testing.setUpSerializers()

    def tearDown(self):
        zope.component.testing.tearDown(self)


class FieldSerializerTest(InsistTest):

    def test_handle_None(self):
        """Test escaping of None values and handling of the escape character
        """

        obj = NoneTestObject()
        store = insist.ConfigurationStore.makeStore(
            obj, INoneTestSchema, 'test')

        # Nones and bangs get escaped:
        self.assertEqual(
            ('[test]\n'
             'test1 = !!None\n'
             'test2 = !None\n'
             'test3 = To infinity!! And beyond!!\n'
             'test4 = !None\n\n'),
             store.dumps())

        # Now let's test the roundtrip:
        store.loads(store.dumps())

        self.assertEqual(u'!None', obj.test1)
        self.assertIsNone(obj.test2)
        self.assertEqual(u'To infinity! And beyond!', obj.test3)
        self.assertIsNone(obj.test4)

    def test_with_None_output(self):
        """A field serialized to None signals exclusion of field.
        """
        class MyList(zope.schema.List):
            pass

        @zope.component.adapter(MyList, zope.interface.Interface)
        class MyListSerializer(insist.ListFieldSerializer):
            def serializeValueWithNone(self, value):
                if value is None or len(value) == 0:
                    return None
                return super(MyListSerializer, self)\
                  .serializeValueWithNone(value)

            def serializeValue(self, value):
                if value is None or len(value) == 0:
                    return None
                return super(MyListSerializer, self).serializeValue(value)

        zope.component.provideAdapter(MyListSerializer)

        class INumbers(zope.interface.Interface):
            numbers = MyList(
                value_type=zope.schema.Int(), required=False)

        class Numbers(object):
            numbers = None

        nums = Numbers()
        nums.numbers = []
        store = insist.ConfigurationStore.makeStore(nums, INumbers, 'numbers')
        self.assertEqual('[numbers]\n\n', store.dumps())


class ConfigurationStoreTest(InsistTest):

    def test_load_missing_values(self):
        """Test that missing configuration values are handled fine.
        """
        obj = NoneTestObject()
        store = insist.ConfigurationStore.makeStore(
            obj, INoneTestSchema, 'test')

        store.loads(
            '[test]\n'
            'test1 = foo\n'
        )

        self.assertEqual(u'foo', obj.test1)
        self.assertIsNone(obj.test2)
        self.assertEqual(u'To infinity! And beyond!', obj.test3)
        self.assertIsNone(obj.test4)

    def test_section(self):
        """The section name defaults to the interface name.
        """
        obj = NoneTestObject()
        store = insist.ConfigurationStore(obj)
        store.schema = INoneTestSchema

        self.assertEqual('INoneTestSchema', store.section)

        store.section = 'specific'
        self.assertEqual('specific', store.section)


    def test_file_header(self):
        """The configurations tore can also place a file header on top
        of the file.
        """
        obj = NoneTestObject()
        store = insist.ConfigurationStore.makeStore(
            obj, INoneTestSchema, 'test')
        store.file_header = '# Nice file header\\n'

        # Nones and bangs get escaped:
        self.assertTrue(
            store.dumps().startswith('# Nice file header'))


class CollectionConfigurationStoreTest(InsistTest):
    """Collection Configuration Store Tests

    This configuration store orchestrates storage of
    collections/mappings. To make the collection store usable a
    few attributes and methods must be provided:
    """

    def test_component(self):

        class SimpleCollectionStore(insist.CollectionConfigurationStore):
            schema = ISimple
            section_prefix = 'simple:'
            item_factory = Simple

        # We also have to register a store for the object itself:

        @zope.component.adapter(ISimple)
        @zope.interface.implementer(interfaces.IConfigurationStore)
        class SimpleStore(insist.ConfigurationStore):
            schema = ISimple

        reg = zope.component.provideAdapter(SimpleStore)

        # Now, let's create a simple collection and create a store for it:

        coll = collections.OrderedDict([
            ('one', Simple(u'Number 1')),
            ('two', Simple(u'Two is a charm')),
            ('three', Simple(u'The tail.'))
            ])

        store = SimpleCollectionStore(coll)

        # Let's have a look at the dump:

        self.assertEqual(
            ('[simple:one]\n'
             'text = Number 1\n'
             '\n'
             '[simple:two]\n'
             'text = Two is a charm\n'
             '\n'
             '[simple:three]\n'
             'text = The tail.\n\n'),
             store.dumps())

        # Now let's test the roundtrip:

        coll2 = {}
        store2 = SimpleCollectionStore(coll2)
        store2.loads(store.dumps())

        self.assertEqual(
            {'one': Simple('Number 1'),
             'three': Simple('The tail.'),
             'two': Simple('Two is a charm')},
            coll2)


class SeparateFileConfigurationStoreTest(InsistTest):
    """Separate File Configuration Store Test

    As the name suggests, this store allows its configuration to be stored in
    a separate file. For this store to work, we need to implement a method
    that tells the store where to store the file:
    """

    def test_component(self):
        import tempfile
        dir = tempfile.mkdtemp()

        class NoneTestStore(insist.SeparateFileConfigurationStore):
            def getConfigPath(self):
                return dir

        # Let's now dump our data:
        obj = NoneTestObject()
        store = NoneTestStore.makeStore(obj, INoneTestSchema, 'test')

        # As we can see, a small stub of the configuration si written to the
        # original store.

        self.assertEqual(
            ('[test]\n'
             'config-file = test.ini\n\n'),
             store.dumps())

        # But the actual data is in the new file, which is named by
        # default like the section:

        with open(os.path.join(dir, 'test.ini')) as file:
            self.assertEqual(
                ('[test]\n'
                 'test1 = !!None\n'
                 'test2 = !None\n'
                 'test3 = To infinity!! And beyond!!\n'
                 'test4 = !None\n\n'),
                 file.read())

        # Let's now load the data again:
        obj2 = NoneTestObject()
        obj2.test1 = obj2.test2 = obj2.test3 = u'Test'
        obj2.test4 = 5
        store2 = NoneTestStore.makeStore(obj2, INoneTestSchema, 'test')

        store2.loads(store.dumps())
        self.assertEqual(u'!None', obj2.test1)
        self.assertIsNone(obj2.test2)
        self.assertEqual(u'To infinity! And beyond!', obj2.test3)
        self.assertIsNone(obj2.test4)

        # We can also tell the store not to leave the stub in the main config
        # file. That requires extra code though to ensure that all config files
        # are loaded.

        store.dumpSectionStub = False
        self.assertEqual('', store.dumps())

        # Finally, in order to ease migration from monolithic configuration
        # files to split files, the store reads the main configuration if it
        # cannot find the file.

        os.remove(os.path.join(dir, 'test.ini'))
        self.assertEqual([], os.listdir(dir))

        obj3 = NoneTestObject()
        obj3.test1 = obj3.test2 = obj3.test3 = u'Test'
        store3 = NoneTestStore.makeStore(obj3, INoneTestSchema, 'test')

        store3.loads(
            '[test]\n'
            'test1 = !!None\n'
            'test2 = !None\n'
            'test3 = To infinity!! And beyond!!\n'
            'test4 = !None\n\n')

        self.assertEqual(u'!None', obj3.test1)
        self.assertIsNone(obj3.test2)
        self.assertEqual(u'To infinity! And beyond!', obj3.test3)
        self.assertIsNone(obj3.test4)


class SeparateFileCollectionConfigurationStoreTest(InsistTest):
    """Separate File Collection Configuration Store Test

    This class is very similar to the regular colelction store except that all
    items are stored in a separate file. So let's do the setup:
    """

    def test_component(self):
        import tempfile
        dir = tempfile.mkdtemp()

        class SimpleCollectionStore(
                insist.SeparateFileCollectionConfigurationStore):

            section = 'simple-collection'
            schema = ISimple
            section_prefix = 'simple:'
            item_factory = Simple

            def getConfigPath(self):
                return dir

        @zope.component.adapter(ISimple)
        @zope.interface.implementer(interfaces.IConfigurationStore)
        class SimpleStore(insist.ConfigurationStore):
            schema = ISimple

        reg = zope.component.provideAdapter(SimpleStore)

        # Now, let's create a simple collection and create a store for it:

        coll = collections.OrderedDict([
            ('one', Simple(u'Number 1')),
            ('two', Simple(u'Two is a charm')),
            ('three', Simple(u'The tail.'))
            ])

        store = SimpleCollectionStore(coll)

        # Let's have a look at the dump:
        self.assertEqual(
            ('[simple-collection]\n'
             'config-file = simple-collection.ini\n\n'),
             store.dumps())

        with open(os.path.join(dir, 'simple-collection.ini')) as file:
            self.assertEqual(
                ('[simple:one]\n'
                'text = Number 1\n'
                '\n'
                '[simple:two]\n'
                'text = Two is a charm\n'
                '\n'
                '[simple:three]\n'
                'text = The tail.\n\n'),
                file.read())

        # Let's now ensure that we can load the data again:
        coll2 = {}
        store2 = SimpleCollectionStore(coll2)
        store2.loads(store.dumps())

        self.assertEqual(
            {'one': Simple(u'Number 1'),
             'three': Simple(u'The tail.'),
             'two': Simple(u'Two is a charm')},
             coll2)


class FileSectionsCollectionConfigurationStoreTest(InsistTest):
    """File Section Configuration Store Test

    If you do not want to store a stub of a section in the main config file,
    you have to provide the collection config store with the ability to
    discover configuration files and only select the correct ones.
    """

    def test_component(self):
        # Let's setup a collection store with its file object store
        # that does not dump the stub.

        import tempfile
        dir = tempfile.mkdtemp()

        class SimpleCollectionStore(
                insist.FileSectionsCollectionConfigurationStore):

            schema = ISimple
            section_prefix = 'simple:'
            item_factory = Simple

            def getConfigPath(self):
                return dir

        @zope.component.adapter(ISimple)
        @zope.interface.implementer_only(interfaces.IConfigurationStore)
        class SimpleStore(insist.SeparateFileConfigurationStore):
            dumpSectionStub = False
            schema = ISimple

            def getConfigPath(self):
                return dir

        reg = zope.component.provideAdapter(SimpleStore)

        # Okay, now things are getting exciting. Let's dump a collection
        # and see what happens:
        coll = collections.OrderedDict([
            ('one', Simple(u'Number 1')),
            ('two', Simple(u'Two is a charm')),
            ('three', Simple(u'The tail.'))
            ])

        store = SimpleCollectionStore(coll)
        self.assertEqual('', store.dumps())

        with open(os.path.join(dir, 'simple:one.ini')) as file:
            self.assertEqual(
                ('[simple:one]\n'
                 'text = Number 1\n\n'),
                 file.read())
        with open(os.path.join(dir, 'simple:two.ini')) as file:
            self.assertEqual(
                ('[simple:two]\n'
                 'text = Two is a charm\n\n'),
                 file.read())
        with open(os.path.join(dir, 'simple:three.ini')) as file:
            self.assertEqual(
                ('[simple:three]\n'
                 'text = The tail.\n\n'),
                 file.read())

        # Now the more interesting part, loading everything again:
        coll2 = {}
        store2 = SimpleCollectionStore(coll2)
        store2.loads(store.dumps())

        self.assertEqual(
            {'one': Simple(u'Number 1'),
             'three': Simple(u'The tail.'),
             'two': Simple(u'Two is a charm')},
             coll2)

        # Also, the config hash of any item is determined by the mod time of
        # all files starting with that section name:

        orig_hash = store.getChildConfigHash(coll['one'], None, 'simple:one')

        info_fn = os.path.join(store.getConfigPath(), 'simple:one.info')
        with open(info_fn, 'w') as file:
           file.write('Info')
        new_hash = store.getChildConfigHash(coll['one'], None, 'simple:one')

        self.assertNotEqual(orig_hash, new_hash)

        os.remove(info_fn)
        new_hash = store.getChildConfigHash(coll['one'], None, 'simple:one')

        self.assertEqual(orig_hash, new_hash)

    def test_getSectionFromPath(self):
        import tempfile
        dir = tempfile.mkdtemp()

        class SimpleCollectionStore(
                insist.FileSectionsCollectionConfigurationStore):

            schema = ISimple
            section_prefix = 'simple:'
            item_factory = Simple

            def getConfigPath(self):
                return dir

        store = SimpleCollectionStore({})

        path = os.path.join(dir, 'simple:section_name.ini')
        with open(path, 'w') as file:
            file.write('')

        self.assertEqual('simple:section_name', store.getSectionFromPath(path))


class CollectionConfigStoreTest(InsistTest):

    def test_dump(self):
        """Collections can be stored semi-automatically
        """

        coll = OrderedDict([
            (u'jeb', Person(u"Jebediah", u"Kerman", 20000, True)),
            (u'val', Person(u"Valentina", u"Kerman", 30000, False)),
        ])
        itemstore = lambda ctx: insist.ConfigurationStore.makeStore(
            ctx, IPerson, 'test')
        gsm = zope.component.getGlobalSiteManager()
        gsm.registerAdapter(
            itemstore, (IPerson, ), interfaces.IConfigurationStore, '')

        store = PersonCollectionStore(coll)
        self.assertEqual(
            ('[person:jeb]\n'
             'firstname = Jebediah\n'
             'lastname = Kerman\n'
             'salary = 20000\n'
             'male = True\n'
             '\n'
             '[person:val]\n'
             'firstname = Valentina\n'
             'lastname = Kerman\n'
             'salary = 30000\n'
             'male = False\n\n'),
             store.dumps())


    def test_load_fresh(self):
        """Load completely new collection
        """

        ini = textwrap.dedent('''
            [person:jeb]
            firstname = Jebediah
            lastname = Kerman
            salary = 20000
            male = True

            [person:val]
            firstname = Valentina
            lastname = Kerman
            salary = 30000
            male = False
        ''')

        itemstore = lambda ctx: insist.ConfigurationStore.makeStore(
            ctx, IPerson, 'test')
        gsm = zope.component.getGlobalSiteManager()
        gsm.registerAdapter(
            itemstore, (IPerson, ), interfaces.IConfigurationStore, '')

        coll = {}
        store = PersonCollectionStore(coll)
        store.loads(ini)

        self.assertEqual(
            {'jeb': Person(u'Jebediah', u'Kerman', 20000, True),
             'val': Person(u'Valentina', u'Kerman', 30000, False)},
             coll)


    def test_load_changeaddremove(self):
        """Add one item and remove another
        """

        # Load initial collection
        ini = textwrap.dedent('''
            [person:jeb]
            firstname = Jebediah
            lastname = Kerman
            salary = 20000
            male = True

            [person:val]
            firstname = Valentina
            lastname = Kerman
            salary = 30000
            male = False
        ''')

        itemstore = lambda ctx: insist.ConfigurationStore.makeStore(
            ctx, IPerson, 'test')
        gsm = zope.component.getGlobalSiteManager()
        gsm.registerAdapter(
            itemstore, (IPerson, ), interfaces.IConfigurationStore, '')

        coll = {}
        store = PersonCollectionStore(coll)
        store.loads(ini)

        self.assertEqual(
            {'jeb': Person(u'Jebediah', u'Kerman', 20000, True),
             'val': Person(u'Valentina', u'Kerman', 30000, False)},
             coll)

        # Save loaded items for future reference

        jeb = coll['jeb']
        val = coll['val']

        # Now let's change the configuration - remove one item and add another

        ini = textwrap.dedent('''
            [person:bill]
            firstname = Bill
            lastname = Kerman
            salary = 30000
            male = True

            [person:val]
            firstname = Valentina
            lastname = Kerman
            salary = 30000
            male = False
        ''')

        store.loads(ini)
        self.assertEqual(
            {'bill': Person(u'Bill', u'Kerman', 30000, True),
             'val': Person(u'Valentina', u'Kerman', 30000, False)},
             coll)

        bill = coll['bill']

        # Make sure we didn't just edit "jeb", but created new item. Also, `val`
        # should stay unchanged.
        self.assertNotEqual(jeb, coll['bill'])
        self.assertEqual(val, coll['val'])

        # Now, change the salary of a bill, and remove val
        ini = textwrap.dedent('''
            [person:bill]
            firstname = Bill
            lastname = Kerman
            salary = 50000
            male = True
        ''')

        store.loads(ini)
        self.assertEqual(
            {'bill': Person(u'Bill', u'Kerman', 50000, True)},
            coll)

        # Bill should not change his identity by this operation
        self.assertEqual(bill, coll['bill'])


    def test_load_typed(self):
        """Test collections with items of different types
        """

        # First, register adapters
        gsm = zope.component.getGlobalSiteManager()

        personstore = lambda ctx: insist.ConfigurationStore.makeStore(
            ctx, IPerson, 'person')
        gsm.registerAdapter(personstore, (IPerson, ),
                            interfaces.IConfigurationStore, '')

        companystore = lambda ctx: insist.ConfigurationStore.makeStore(
            ctx, ICompany, 'company')
        gsm.registerAdapter(companystore, (ICompany, ),
                            interfaces.IConfigurationStore, '')

        coll = {}
        store = MixedClassCollectionStore(coll)

        # Load initial data
        ini = textwrap.dedent('''
            [item:jeb]
            type = person
            firstname = Jebediah
            lastname = Kerman
            salary = 20000
            male = True

            [item:pp]
            type = company
            name = Pied Piper, Inc
        ''')
        store.loads(ini)

        self.assertEqual(
            {'jeb': Person(u'Jebediah', u'Kerman', 20000, True),
             'pp': Company(u'Pied Piper, Inc')},
             coll)

        # Now, suddenly, jeb becomes a company

        ini = textwrap.dedent('''
            [item:jeb]
            type = company
            name = Jeb Startup, Inc

            [item:pp]
            type = company
            name = Pied Piper, Inc
        ''')
        store.loads(ini)

        self.assertEqual(
            {'jeb': Company(u'Jeb Startup, Inc'),
             'pp': Company(u'Pied Piper, Inc')},
             coll)


class ListFieldSerializerTest(InsistTest):
    """Tuple and list fields are serialized as multiline values.
    """

    def test_None(self):
        """Check that None gets serialized and can be read back
        """
        class INumbers(zope.interface.Interface):
            numbers = zope.schema.List(
                value_type=zope.schema.Int())

        class Numbers(object):
            numbers = None

        nums = Numbers()
        nums.numbers = [42, None]
        store = insist.ConfigurationStore.makeStore(nums, INumbers, 'numbers')

        self.assertEqual(
            ('[numbers]\n'
             'numbers = 42, !!None\n\n'),
             store.dumps())

    def test_double_escape(self):
        """Well it gets double escaped... But it won't fail loading
        """
        class INumbers(zope.interface.Interface):
            numbers = zope.schema.List(
                value_type=zope.schema.Int())

        class Numbers(object):
            numbers = None

        nums = Numbers()
        nums.numbers = [42, None]
        store = insist.ConfigurationStore.makeStore(nums, INumbers, 'numbers')

        store.loads(textwrap.dedent('''
            [numbers]
            numbers = 42, !!None
        '''))

        self.assertEqual([42, None], nums.numbers)

        store.loads(textwrap.dedent('''
            [numbers]
            numbers =
        '''))
        self.assertEqual([], nums.numbers)

    def test_separator_in_item(self):
        '''Check what happens when there\'s a separator in an item
        '''
        class ISomeTexts(zope.interface.Interface):
            sometexts = zope.schema.List(
                value_type=zope.schema.TextLine())

        class SomeTexts(object):
            sometexts = None

        texts = SomeTexts()
        texts.sometexts = [u'42', None, u', ', u'foo']
        store = insist.ConfigurationStore.makeStore(
            texts, ISomeTexts, 'sometexts')

        self.assertEqual(
            ('[sometexts]\n'
             'sometexts = 42, !!None, , , foo\n\n'),
             store.dumps())

        store.loads(textwrap.dedent('''
            [sometexts]
            sometexts = 42, !!None, , , foo
        '''))

        # oooooooooops, that u', ' we sent in is gone... don't try this at home

        self.assertEqual(
            [u'42', None, u'', u'', u'foo'],
            texts.sometexts)


    def test_list_value_type(self):
        '''Let\'s see what happens is value_type is List
        '''
        class IPerson(zope.interface.Interface):
            somedata = zope.schema.List(
                value_type=zope.schema.Dict(
                    key_type=zope.schema.TextLine(),
                    value_type=zope.schema.TextLine()))

        class Person(object):
            somedata = None

        p = Person()
        store = insist.ConfigurationStore.makeStore(p, IPerson, 'person')

        p.somedata = [
            collections.OrderedDict([
                (u'first', u'foo')
            ]),
            collections.OrderedDict([
              (u'second', u'bar'), (u'third', u'fun')
            ]),
        ]
        self.assertEqual(
            ('[person]\n'
             'somedata = first::foo, second::bar\n'
             '\tthird::fun\n\n'),
             store.dumps())

        store.loads(store.dumps())
        self.assertEqual(
            [{u'first': u'foo'}, {u'second': u'bar', u'third': u'fun'}],
            p.somedata)


class DictFieldSerializerTest(InsistTest):
    """Dict fields get JSONified.
    """

    def setUp(self):
        super(DictFieldSerializerTest, self).setUp()

        class IPerson(zope.interface.Interface):
            somedata = zope.schema.Dict(
                key_type=zope.schema.TextLine(),
                value_type=zope.schema.Int())

        class Person(object):
            somedata = None

        self.person = Person()
        self.store = insist.ConfigurationStore.makeStore(
            self.person, IPerson, 'person')


    def test_None_foo(self):
        """Check what happens with None
        """
        self.person.somedata = None
        self.assertEqual(
            ('[person]\n'
             'somedata = !None\n\n'),
             self.store.dumps())

        self.person.somedata = OrderedDict([
            (u'foo', 42),
            (u'bar', None)])
        self.assertEqual(
            ('[person]\n'
             'somedata = foo::42\n'
             '\tbar::!!None\n\n'),
             self.store.dumps())

        self.store.loads(textwrap.dedent('''
            [person]
            somedata = !None
        '''))
        self.assertIsNone(self.person.somedata)

        self.store.loads(textwrap.dedent('''
            [person]
            somedata =
        '''))
        self.assertEqual({}, self.person.somedata)

    def test_None_in_value_type(self):
        """Check what happens with None in value type
        """
        self.store.loads(textwrap.dedent('''
            [person]
            somedata = bar::15
                foo::!!None
        '''))
        self.assertEqual(
            {u'bar': 15,
             u'foo': None},
            self.person.somedata)

    def test_edge_cases(self):
        """Check some strange edge cases
        """
        with self.assertRaises(ValueError):
            self.store.loads(textwrap.dedent('''
                [person]
                somedata = {}
            '''))

        with self.assertRaises(ValueError):
            self.store.loads(textwrap.dedent('''
                [person]
                somedata = ::
            '''))

        self.store.loads(textwrap.dedent('''
             [person]
             somedata = ::42
        '''))
        self.assertEqual({u'': 42}, self.person.somedata)

        self.store.loads(textwrap.dedent('''
             [person]
             somedata =
                 bar::42
        '''))
        self.assertEqual({u'bar': 42}, self.person.somedata)

    def test_separator(self):
        """Separator in key_type or value_type fails

        Choose your separator wisely
        """
        with self.assertRaises(ValueError):
            self.store.loads(textwrap.dedent('''
                [person]
                somedata =
                    ba::r::42
             '''))

    def test_factory_OrderedDict(self):
        '''OrderedDict as factory
        '''
        save_factory = insist.DictFieldSerializer.factory
        insist.DictFieldSerializer.factory = OrderedDict

        self.store.loads(textwrap.dedent('''
             [person]
             somedata =
                 bar::42
        '''))
        self.assertEqual(
            {u'bar': 42},
            self.person.somedata)

        self.store.loads(textwrap.dedent('''
            [person]
            somedata = bar::42
                foo::666
        '''))

        self.assertEqual(
            OrderedDict([(u'bar', 42), (u'foo', 666)]),
            self.person.somedata)

        self.store.loads(textwrap.dedent('''
            [person]
            somedata = foo::402
                bar::987
        '''))

        self.assertEqual(
            OrderedDict([(u'foo', 402), (u'bar', 987)]),
            self.person.somedata)

        insist.DictFieldSerializer.factory = save_factory

    def test_value_type_Date(self):
        '''Check Date as value_type'''

        class IPerson(zope.interface.Interface):
            somedata = zope.schema.Dict(
                key_type=zope.schema.TextLine(),
                value_type=zope.schema.Date())

        class Person(object):
            somedata = None

        p = Person()
        store = insist.ConfigurationStore.makeStore(p, IPerson, 'person')

        p.somedata = collections.OrderedDict([
           (u'foo', datetime.date(2015, 11, 7)), (u'bar', None)
        ])
        self.assertEqual(
            ('[person]\n'
             'somedata = foo::2015-11-07\n'
             '\tbar::!!None\n\n'),
             store.dumps())

        store.loads(textwrap.dedent('''
            [person]
            somedata = !None
        '''))
        self.assertIsNone(p.somedata)

        store.loads(textwrap.dedent('''
            [person]
            somedata =
        '''))
        self.assertEqual({}, p.somedata)

        store.loads(textwrap.dedent('''
            [person]
            somedata = foo::2015-11-07
                bar::!!None
        '''))
        self.assertEqual(
            {u'bar': None,
             u'foo': datetime.date(2015, 11, 7)},
            p.somedata)

        # What happens when value_type does not conform?
        with self.assertRaises(ValueError):
            store.loads(textwrap.dedent('''
                [person]
                somedata = foo::42
                    bar::!!None
            '''))

    def test_unicode_key_value(self):
        '''Let\'s see that unicode strings survive dump and load.
        '''
        self.person.somedata = {u'foo\u07d0': None}
        self.store.loads(self.store.dumps())
        self.assertEqual(
            {u'foo\u07d0': None},
            self.person.somedata)

    def test_newline(self):
        '''Let\'s see that \n and friends survive load and dump.
        '''
        class IPerson(zope.interface.Interface):
            somedata = zope.schema.Dict(
                key_type=zope.schema.TextLine(),
                value_type=zope.schema.Text())

        class Person(object):
            somedata = None

        p = Person()
        p.somedata = {u'foo': 'first\nsecond\rthird\ta tab'}
        store = insist.ConfigurationStore.makeStore(p, IPerson, 'person')

        self.assertEqual(
            ('[person]\n'
             'somedata = foo::first\\nsecond\\rthird\\ta tab\n\n'),
             store.dumps())

        store.loads(store.dumps())
        self.assertEqual(
            {u'foo': u'first\nsecond\rthird\ta tab'},
            p.somedata)

    def test_value_type_List(self):
        '''Let\'s see what happens is value_type is List
        '''
        class IPerson(zope.interface.Interface):
            somedata = zope.schema.Dict(
                key_type=zope.schema.TextLine(),
                value_type=zope.schema.List(
                    value_type=zope.schema.TextLine()))

        class Person(object):
            somedata = None

        p = Person()
        p.somedata = {u'foo': [u'first', u'second']}
        store = insist.ConfigurationStore.makeStore(p, IPerson, 'person')

        self.assertEqual(
            ('[person]\n'
             'somedata = foo::first, second\n\n'),
             store.dumps())

        store.loads(store.dumps())
        self.assertEqual(
            {u'foo': [u'first', u'second']},
            p.somedata)


def setUp(test):
    zope.component.testing.setUp(test)
    testing.setUpSerializers()


def tearDown(test):
    zope.component.testing.tearDown(test)


def test_suite():
    optionflags=(doctest.NORMALIZE_WHITESPACE|
                 doctest.REPORT_NDIFF|
                 doctest.ELLIPSIS)

    return unittest.TestSuite([
        doctest.DocFileSuite(
            '../insist.txt',
            setUp=setUp, tearDown=tearDown, optionflags=optionflags),
        unittest.makeSuite(FieldSerializerTest),
        unittest.makeSuite(ConfigurationStoreTest),
        unittest.makeSuite(CollectionConfigurationStoreTest),
        unittest.makeSuite(SeparateFileConfigurationStoreTest),
        unittest.makeSuite(SeparateFileCollectionConfigurationStoreTest),
        unittest.makeSuite(FileSectionsCollectionConfigurationStoreTest),
        unittest.makeSuite(CollectionConfigStoreTest),
        unittest.makeSuite(ListFieldSerializerTest),
        unittest.makeSuite(DictFieldSerializerTest),
    ])
