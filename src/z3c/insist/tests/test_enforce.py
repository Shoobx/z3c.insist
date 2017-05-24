###############################################################################
#
# Copyright 2013-15 by Shoobx, Inc.
#
###############################################################################
"""Enforcer -- File listener and config executor.

Test fixture.
"""
from __future__ import print_function

import doctest
import io
import logging
import mock
import os
import sys
import unittest
import watchdog.events
import zope.component
import zope.interface
from watchdog.observers.api import ObservedWatch

from z3c.insist import enforce, insist, interfaces, testing

PY3 = sys.version_info.major >= 3

if PY3:
    _u = str
else:
    _u = unicode

test_logger = logging.getLogger(__name__)


class SampleHandler(watchdog.events.FileSystemEventHandler):

    def on_modified(self, event):
        test_logger.info(_u(event))

    def on_created(self, event):
        test_logger.info(_u(event))

    def on_deleted(self, event):
        test_logger.info(_u(event))


class EventQueue(object):

    def __init__(self, event):
        self.event = event

    def get(self, block, timeout):
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
            EventQueue(watchdog.events.FileModifiedEvent('./sample.ini')), 1)
        self.assertEqual(
            "<FileModifiedEvent: src_path='./sample.ini'>\n",
            self.log.getvalue())

        # Now we are locking the directory, ...
        enf.dispatch_events(
            EventQueue(watchdog.events.FileCreatedEvent('./lock')), 1)

        # so no event come through:
        enf.dispatch_events(
            EventQueue(watchdog.events.FileModifiedEvent('./sample.ini')), 1)

        # Once we unlock the directory, everything flows again:
        enf.dispatch_events(
            EventQueue(watchdog.events.FileDeletedEvent('./lock')), 1)

        self.log.__init__(u'')
        enf.dispatch_events(
            EventQueue(watchdog.events.FileModifiedEvent('./sample.ini')), 1)
        self.assertEqual(
            "<FileModifiedEvent: src_path='./sample.ini'>\n",
            self.log.getvalue())


class EnforcerFileSectionsCollectionStore(EnforcerBaseTest):
    """Enforcer File Sections Collection Store Tests
    """

    def test_component(self):
        # This small mix-in class provides the necessary functions for
        # a store to work the enforcer. So let's say I have this
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


class FileSectionsEnforcerEventHandler(EnforcerBaseTest):
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
        unittest.makeSuite(EnforcerFileSectionsCollectionStore),
        unittest.makeSuite(EnforcerEventHandlerTest),
        unittest.makeSuite(FileSectionsEnforcerEventHandler),
        unittest.makeSuite(SeparateFileEnforcerEventHandlerTest),
    ])
