###############################################################################
#
# Copyright 2013-15 by Shoobx, Inc.
#
###############################################################################
"""Enforcer -- File listener and config executor.

Test fixture.
"""
import doctest
import io
import logging
import mock
import os
import pathlib
import sys
import tempfile
import time
import unittest
import watchdog.events
import zope.component
import zope.interface
from watchdog.observers.api import ObservedWatch

from z3c.insist import enforce, insist, interfaces, testing


test_logger = logging.getLogger(__name__)


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


class SampleHandler(watchdog.events.FileSystemEventHandler):

    def on_modified(self, event):
        test_logger.info(str(event))

    def on_created(self, event):
        test_logger.info(str(event))

    def on_deleted(self, event):
        test_logger.info(str(event))


class EventQueue(object):

    def __init__(self, event):
        self.event = event

    def get(self, block):
        return self.event, ObservedWatch('./', True)

    def task_done(self):
        pass


class EnforcerBaseTest(unittest.TestCase):

    def setUp(self):
        zope.component.testing.setUp(self)
        testing.setUpSerializers()
        # Setup logging
        self.log = io.StringIO()
        handler = logging.StreamHandler(self.log)
        handler._added_by_tests_ = True
        handler._old_propagate_ = test_logger.propagate
        handler._old_level_ = test_logger.level
        handler.setFormatter(logging.Formatter('%(message)s'))
        test_logger.addHandler(handler)
        test_logger.propagate = False
        test_logger.setLevel(logging.INFO)

    def tearDown(self):
        zope.component.testing.tearDown(self)
        # Tear down logging.
        for handler in list(test_logger.handlers):
            if hasattr(handler, '_added_by_tests_'):
                test_logger.removeHandler(handler)
                test_logger.propagate = handler._old_propagate_
                test_logger.setLevel(handler._old_level_)


class EnforcerTest(EnforcerBaseTest):
    """Base Enforcer Test
    """

    def test_component(self):
        # We are using watchdog to listen for changed to the filesystem in a
        # particular directory. The first argument is the target directory.

        enf = enforce.Enforcer('./')

        # To start with, we have to register at least one config store
        # event handler.
        handler = mock.Mock()
        enf.schedule = mock.Mock()
        enf.register(handler)

        enf.schedule.assert_called_with(handler, path='./', recursive=True)

        # Of course, this is not how we ususally register
        # handlers. The enforcer is capable of complete self-discovery
        # via ZCA. This allows us not to worry about additional
        # reggistrations purely for the purpose of the enforcer.

        @zope.component.adapter(zope.interface.Interface)
        @zope.interface.implementer_only(interfaces.IConfigurationStore)
        class NumbersStore(insist.SeparateFileCollectionConfigurationStore,
                           enforce.EnforcerFileSectionsCollectionStore):
            section = 'numbers'
            section_prefix = 'number:'

        zope.component.provideAdapter(NumbersStore)

        enf = enforce.Enforcer('./')
        enf.registerHandlers()

        watcher, handlers = list(enf._handlers.items())[0]
        handler = tuple(handlers)[0]
        self.assertEqual('./', watcher.path)
        self.assertTrue(watcher.is_recursive)
        self.assertEqual(NumbersStore, handler.factory)

        # Now that we have a handler, we can start the enforcer. Note
        # that enforcers are just a small extension to watchdog
        # observers, so the API is identical:
        enf.start = lambda: None
        enf.start()

        # At this point a thread would be started listening for
        # inotify events. The thread can be shut down as follows:
        enf.stop = lambda: None
        enf.stop()

    def test_locking(self):
        """Enforcer Locking Support
        """
        # The enforcer will mark a directory as locked when loading
        # the configuration. This allows one to block other load and
        # write operations on that config while loading.
        enf = enforce.Enforcer('./')
        enf.register(SampleHandler())

        # Lockfiles have the following name:
        enf.lockFilename
        'lock'

        # Before locking, handlers do their usual work:
        evt = enf.dispatch_events(
            EventQueue(watchdog.events.FileModifiedEvent('./sample.ini')))
        self.assertEqual(
            "<FileModifiedEvent:"
            " event_type=modified,"
            " src_path='./sample.ini',"
            " is_directory=False>\n",
            self.log.getvalue())

        # Now we are locking the directory, ...
        enf.dispatch_events(
            EventQueue(watchdog.events.FileCreatedEvent('./lock')))

        # so no event come through:
        enf.dispatch_events(
            EventQueue(watchdog.events.FileModifiedEvent('./sample.ini')))

        # Once we unlock the directory, everything flows again:
        enf.dispatch_events(
            EventQueue(watchdog.events.FileDeletedEvent('./lock')))

        self.log.__init__('')
        enf.dispatch_events(
            EventQueue(watchdog.events.FileModifiedEvent('./sample.ini')))
        self.assertEqual(
            "<FileModifiedEvent:"
            " event_type=modified,"
            " src_path='./sample.ini',"
            " is_directory=False>\n",
            self.log.getvalue())

    def test_included(self):

        baseDir = pathlib.Path(tempfile.mkdtemp('-base'))
        basePath = baseDir.joinpath('simple-collection.ini')
        basePath.write_text(
            '[simple:one]\n'
            'text = One\n'
            '\n'
            '[simple:two]\n'
            'text = Two\n'
            )

        nestedConfDir = pathlib.Path(tempfile.mkdtemp(suffix='-nestedConf', dir=baseDir))
        # baseDir/tmpdir-nestedConf/simple-collection.ini
        nestedPath = nestedConfDir.joinpath('simple-collection.ini')
        nestedPath.write_text(
            '[simple:five]\n'
            'text = 5\n'
            '\n'
            '[simple:six]\n'
            'text = 6\n'
            )

        baseConfDir = pathlib.Path(tempfile.mkdtemp('-baseConf', dir=baseDir))
        confDir = pathlib.Path(tempfile.mkdtemp('-conf', dir=baseConfDir))
        simplePath = confDir.joinpath('simple-collection.ini')
        simplePath.write_text(
            f'#include {basePath}\n'
            #   ../../tmpdir-nestedConf/simple-collection.ini
            # baseDir/
            f'#include ../../{nestedPath.relative_to(baseDir)}\n'
            '[simple:two]\n'
            'text = 2\n'
            '\n'
            '[simple:three]\n'
            'text = 3\n'
            )

        coll = {}

        @zope.component.adapter(dict)
        @zope.interface.implementer_only(interfaces.IConfigurationStore)
        class SimpleCollectionStore(
                insist.SeparateFileCollectionConfigurationStore,
                enforce.EnforcerFileSectionsCollectionStore
        ):

            section = 'simple-collection'
            schema = ISimple
            section_prefix = 'simple:'
            item_factory = Simple

            def getConfigPath(self):
                return baseConfDir
            
            def getConfigFilename(self):
                return simplePath.relative_to(baseConfDir)  

            @classmethod
            def fromRootAndFilename(cls, root, filename=None):
                return cls(coll)

        zope.component.provideAdapter(SimpleCollectionStore)

        @zope.component.adapter(ISimple)
        @zope.interface.implementer(interfaces.IConfigurationStore)
        class SimpleStore(insist.ConfigurationStore):
            dumpSectionStub = False
            schema = ISimple

            def getConfigPath(self):
                return baseConfDir

        zope.component.provideAdapter(SimpleStore)

        enf = enforce.Enforcer(baseConfDir, coll)
        enf.registerHandlers()
        enf.start()

        inc = enforce.IncludeObserver(baseConfDir)
        inc.initialize()
        inc.start()

        # Load the configuration when the main config file is modified.
        simplePath.touch()
        time.sleep(0.01)
        self.assertEqual(len(coll), 5)
        self.assertEqual(coll['one'].text, 'One')
        self.assertEqual(coll['two'].text, '2')
        self.assertEqual(coll['three'].text, '3')
        self.assertEqual(coll['five'].text, '5')
        self.assertEqual(coll['six'].text, '6')

        # Configuration should also be loaded when the base config file is
        # updated.
        basePath.write_text(
            '[simple:one]\n'
            'text = 1\n'
        )
        time.sleep(0.01)
        self.assertEqual(len(coll), 5)
        self.assertEqual(coll['one'].text, '1')

        # Configuration should also be loaded when base config included using
        # relative path is updated.
        nestedPath.write_text(
            '[simple:five]\n'
            'text = five\n'
        )
        time.sleep(0.01)
        self.assertEqual(len(coll), 4)
        self.assertEqual(coll['five'].text, 'five')

        # Add a new base file and remove relative one.
        baseDir2 = pathlib.Path(tempfile.mkdtemp('-base2'))
        basePath2 = baseDir2.joinpath('simple-collection.ini')
        basePath2.write_text(
            '[simple:four]\n'
            'text = Four\n'
        )
        simplePath.write_text(
            f'#include {basePath}\n'
            f'#include {basePath2}\n'
            '[simple:two]\n'
            'text = 2\n'
            '\n'
            '[simple:three]\n'
            'text = 3\n'
        )
        time.sleep(0.01)

        self.assertEqual(len(coll), 4)
        self.assertEqual(coll['one'].text, '1')
        self.assertEqual(coll['two'].text, '2')
        self.assertEqual(coll['three'].text, '3')
        self.assertEqual(coll['four'].text, 'Four')

        # Modify the newly added base.
        basePath2.write_text(
            '[simple:four]\n'
            'text = 4\n'
        )
        time.sleep(0.01)
        self.assertEqual(coll['four'].text, '4')

        # Remove second base.
        simplePath.write_text(
            f'#include {basePath}\n'
            '[simple:two]\n'
            'text = 2\n'
            '\n'
            '[simple:three]\n'
            'text = 3\n'
        )
        os.remove(basePath2)
        time.sleep(0.01)

        self.assertEqual(len(coll), 3)
        self.assertEqual(coll['one'].text, '1')
        self.assertEqual(coll['two'].text, '2')
        self.assertEqual(coll['three'].text, '3')

        inc.stop()
        inc.join()
        enf.stop()
        enf.join()


class EnforcerFileSectionsCollectionStoreTest(EnforcerBaseTest):
    """Enforcer File Sections Collection Store Tests
    """

    def test_component(self):
        # This small mix-in class provides the necessary functions for
        # a store to work ,vb   the enforcer. So let's say I have this
        # simple store:
        class NumbersStore(enforce.EnforcerFileSectionsCollectionStore):
            section = 'numbers'
            section_prefix = 'number:'

            def getSectionFromPath(self, path):
                return os.path.split(path)[-1][:-4]

        # We can now create the store and ask for the files to listen for:
        store = NumbersStore()
        store.getFilePatterns()
        ['*/numbers.ini', '*/number:*.*']

        # Once the event handler triggers, the store is instantiated
        # using the following API call, which must be implemented by
        # sub-classes:
        root = {}
        with self.assertRaises(NotImplementedError):
            NumbersStore.fromRootAndFilename(root, './number:1.ini')


class EnforcerEventHandlerTest(EnforcerBaseTest):
    """Enforcer Event Handler

    This event handler looks up all adapters registered to provide
    `IConfigurationStore` and checks whether the factory support the
    enforcer. If so, it adds the factory to its local registry of
    participating stores.
    """

    def test_component(self):
        config = mock.Mock()
        store = mock.Mock()
        store.section_prefix = 'number:'
        store._createConfigParser = mock.Mock(return_value=config)
        store.loadFromSection = mock.Mock()
        store.deleteItem = mock.Mock()

        class NumbersStore(enforce.EnforcerFileSectionsCollectionStore):
            section = 'numbers'
            section_prefix = 'number:'

            @classmethod
            def fromRootAndFilename(cls, root, filename=None):
                return cls()

            def getSectionFromPath(self, path):
                return os.path.split(path)[-1][:-4]

            _createConfigParser = mock.Mock(return_value=config)
            loadFromSection = mock.Mock()
            deleteItem = mock.Mock()

        zope.component.provideAdapter(
            NumbersStore, (zope.interface.Interface,),
            interfaces.IConfigurationStore)

        reg = mock.Mock()
        reg.factory = NumbersStore
        handler = enforce.EnforcerEventHandler(reg)

        # Let's now dispatch events to see how the store get's called:

        # 1. File Creation:
        evt = watchdog.events.FileCreatedEvent('./path/number:1.ini')
        with self.assertRaises(NotImplementedError):
            handler.dispatch(evt)

        # 2. File Modification
        evt = watchdog.events.FileModifiedEvent('./path/number:1.ini')
        with self.assertRaises(NotImplementedError):
            handler.dispatch(evt)

        # 3. File Deletion
        evt = watchdog.events.FileDeletedEvent('./path/number:1.ini')
        with self.assertRaises(NotImplementedError):
            handler.dispatch(evt)


class FileSectionsEnforcerEventHandlerTest(EnforcerBaseTest):
    """File Sections Enforcer Event Handler
    """

    def test_component(self):
        config = mock.Mock()
        store = mock.Mock()
        store.section_prefix = 'number:'
        store._createConfigParser = mock.Mock(return_value=config)
        store.loadFromSection = mock.Mock()
        store.deleteItem = mock.Mock()

        class NumbersStore(enforce.EnforcerFileSectionsCollectionStore):
            section = 'numbers'
            section_prefix = 'number:'
            root = 'root'

            @classmethod
            def fromRootAndFilename(cls, root, filename=None):
                return cls()

            def getSectionFromPath(self, path):
                return os.path.split(path)[-1][:-4]

            _createConfigParser = mock.Mock(return_value=config)
            loadFromSection = mock.Mock()
            deleteItem = mock.Mock()

        zope.component.provideAdapter(
            NumbersStore, (zope.interface.Interface,),
            interfaces.IConfigurationStore)

        reg = mock.Mock()
        reg.factory = NumbersStore
        handler = enforce.FileSectionsEnforcerEventHandler(reg)

        # Let's now dispatch events to see how the store get's called:

        # 1. File Creation:
        evt = watchdog.events.FileCreatedEvent('./path/number:1.ini')
        self.assertTrue(handler.dispatch(evt))
        NumbersStore.loadFromSection.assert_called_with(config, 'number:1')

        # 2. File Modification
        NumbersStore.loadFromSection.reset_mock()
        evt = watchdog.events.FileModifiedEvent('./path/number:1.ini')
        self.assertTrue(handler.dispatch(evt))
        NumbersStore.loadFromSection.assert_called_with(config, 'number:1')

        # 3. File Deletion
        store.reset_mock()
        evt = watchdog.events.FileDeletedEvent('./path/number:1.ini')
        self.assertTrue(handler.dispatch(evt))
        NumbersStore.deleteItem.assert_called_with('1')

        # 4. File Opened, we ignore this event and do nothing.
        store.reset_mock()
        evt = watchdog.events.FileOpenedEvent('./path/number:1.ini')
        self.assertFalse(handler.dispatch(evt))

        # If no store is found, we simply return and do nothing:
        NumbersStore.loadFromSection.reset_mock()
        evt = watchdog.events.FileCreatedEvent('./path/int:1.ini')
        self.assertFalse(handler.dispatch(evt))
        self.assertFalse(NumbersStore.loadFromSection.called)


class SeparateFileEnforcerEventHandlerTest(EnforcerBaseTest):
    """Separate File Enforcer Event Handler
    """

    def test_component(self):
        config = mock.Mock()

        class NumbersStore(enforce.EnforcerFileSectionsCollectionStore):
            section = 'numbers'
            section_prefix = 'number:'
            root = 'root'

            @classmethod
            def fromRootAndFilename(cls, root, filename=None):
                return cls()

            def getSectionFromPath(self, path):
                return os.path.split(path)[-1][:-4]

            _createConfigParser = mock.Mock(return_value=config)
            load = mock.Mock()
            deleteItem = mock.Mock()

        zope.component.provideAdapter(
            NumbersStore, (zope.interface.Interface,),
            interfaces.IConfigurationStore)

        reg = mock.Mock()
        reg.factory = NumbersStore
        handler = enforce.SeparateFileEnforcerEventHandler(reg)

        # Let's now dispatch events to see how the store get's called:

        # 1. File Creation:
        evt = watchdog.events.FileCreatedEvent('./path/number:1.ini')
        self.assertTrue(handler.dispatch(evt))
        NumbersStore.load.assert_called_with(config)

        # 2. File Modification
        NumbersStore.load.reset_mock()
        evt = watchdog.events.FileModifiedEvent('./path/number:1.ini')
        self.assertTrue(handler.dispatch(evt))
        NumbersStore.load.assert_called_with(config)

        # 3. File Deletion - Error is logged, since deleting those
        # files amkes no sense.
        evt = watchdog.events.FileDeletedEvent('./path/number:1.ini')
        self.assertTrue(handler.dispatch(evt))

        # If no store is found, we simply return and do nothing:
        NumbersStore.load.reset_mock()
        evt = watchdog.events.FileCreatedEvent('./path/int:1.ini')
        self.assertFalse(handler.dispatch(evt))
        self.assertFalse(NumbersStore.load.called)


def test_suite():
    return unittest.TestSuite([
        unittest.makeSuite(EnforcerTest),
        unittest.makeSuite(EnforcerFileSectionsCollectionStoreTest),
        unittest.makeSuite(EnforcerEventHandlerTest),
        unittest.makeSuite(FileSectionsEnforcerEventHandlerTest),
        unittest.makeSuite(SeparateFileEnforcerEventHandlerTest),
    ])
