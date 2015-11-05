###############################################################################
#
# Copyright 2013-15 by Shoobx, Inc.
#
###############################################################################
"""Enforcer -- File listener and config executor.

Test fixture.
"""
import doctest
import mock
import unittest
import watchdog.events
import zope.component
import zope.interface

from z3c.insist import enforce, insist, interfaces, testing


def doctest_Enforcer():
    r"""Base Enforcer Test

    We are using watchdog to listen for changed to the filesystem in a
    particular directory. The first argument is the target directory.

    >>> enf = enforce.Enforcer('./')

    To start with, we have to register at least one config store event handler.

    >>> handler = mock.Mock()
    >>> enf.schedule = mock.Mock()
    >>> enf.register(handler)

    >>> enf.schedule.assert_called_with(handler, path='./', recursive=True)

    Of course, this is not how we ususally register handlers. The enforcer is
    capable of complete self-discovery via ZCA. This allows us not to worry
    about additional reggistrations purely for the purpose of the enforcer.

    >>> @zope.component.adapter(zope.interface.Interface)
    ... @zope.interface.implementer_only(interfaces.IConfigurationStore)
    ... class NumbersStore(insist.SeparateFileCollectionConfigurationStore,
    ...                    enforce.EnforcerFileSectionsCollectionStore):
    ...     section = 'numbers'
    ...     section_prefix = 'number:'
    >>> zope.component.provideAdapter(NumbersStore)

    >>> enf = enforce.Enforcer('./')
    >>> enf.registerHandlers()

    >>> enf._handlers
    {<ObservedWatch: path=./, is_recursive=True>:
        set([<z3c.insist.enforce.SeparateFileEnforcerEventHandler ...>])}

    Now that we have a handler, we can start the enforcer. Note that enforcers
    are just a small extension to watchdog observers, so the API is identical:

    >>> enf.start = lambda: None
    >>> enf.start()

    At this point a thread would be started listening for inotify events. The
    thread can be shut down as follows:

    >>> enf.stop = lambda: None
    >>> enf.stop()
    """

def doctest_EnforcerFileSectionsCollectionStore():
    """Enforcer File Sections Collection Store Tests

    This small mix-in class provides the necessary functions for a store to
    work the enforcer. So let's say I have this simple store:

    >>> class NumbersStore(enforce.EnforcerFileSectionsCollectionStore):
    ...     section = 'numbers'
    ...     section_prefix = 'number:'

    We can now create the store and ask for the files to listen for:

    >>> store = NumbersStore()
    >>> store.getFilePatterns()
    ['*/numbers.ini', '*/number:*.*']

    Once the event handler triggers, the store is instantiated using the
    following API call, which must be implemented by sub-classes:

    >>> root = {}
    >>> NumbersStore.fromRootAndFilename(root, './number:1.ini')
    Traceback (most recent call last):
    ...
    NotImplementedError: Create store from root and filename.
    """


def doctest_EnforcerEventHandler():
    """Enforcer Event Handler

    This event handler looks up all adapters registered to provide
    `IConfigurationStore` and checks whether the factory support the
    enforcer. If so, it adds the factory to its local registry of
    participating stores.

    >>> config = mock.Mock()
    >>> store = mock.Mock()
    >>> store.section_prefix = 'number:'
    >>> store._createConfigParser = mock.Mock(return_value=config)
    >>> store.loadFromSection = mock.Mock()
    >>> store.deleteItem = mock.Mock()

    >>> class NumbersStore(enforce.EnforcerFileSectionsCollectionStore):
    ...     section = 'numbers'
    ...     section_prefix = 'number:'
    ...
    ...     @classmethod
    ...     def fromRootAndFilename(cls, root, filename=None):
    ...         return cls()
    ...
    ...     _createConfigParser = mock.Mock(return_value=config)
    ...     loadFromSection = mock.Mock()
    ...     deleteItem = mock.Mock()

    >>> zope.component.provideAdapter(
    ...     NumbersStore, (zope.interface.Interface,),
    ...     interfaces.IConfigurationStore)

    >>> reg = mock.Mock()
    >>> reg.factory = NumbersStore

    >>> handler = enforce.EnforcerEventHandler(reg)

    Let's now dispatch events to see how the store get's called:

    1. File Creation:

    >>> evt = watchdog.events.FileCreatedEvent('./path/number:1.ini')
    >>> handler.dispatch(evt)
    Traceback (most recent call last):
    ...
    NotImplementedError

    2. File Modification

    >>> evt = watchdog.events.FileModifiedEvent('./path/number:1.ini')
    >>> handler.dispatch(evt)
    Traceback (most recent call last):
    ...
    NotImplementedError

    3. File Deletion

    >>> evt = watchdog.events.FileDeletedEvent('./path/number:1.ini')
    >>> handler.dispatch(evt)
    Traceback (most recent call last):
    ...
    NotImplementedError
    """


def doctest_FileSectionsEnforcerEventHandler():
    """File Sections Enforcer Event Handler

    >>> config = mock.Mock()
    >>> store = mock.Mock()
    >>> store.section_prefix = 'number:'
    >>> store._createConfigParser = mock.Mock(return_value=config)
    >>> store.loadFromSection = mock.Mock()
    >>> store.deleteItem = mock.Mock()

    >>> class NumbersStore(enforce.EnforcerFileSectionsCollectionStore):
    ...     section = 'numbers'
    ...     section_prefix = 'number:'
    ...
    ...     @classmethod
    ...     def fromRootAndFilename(cls, root, filename=None):
    ...         return cls()
    ...
    ...     _createConfigParser = mock.Mock(return_value=config)
    ...     loadFromSection = mock.Mock()
    ...     deleteItem = mock.Mock()

    >>> zope.component.provideAdapter(
    ...     NumbersStore, (zope.interface.Interface,),
    ...     interfaces.IConfigurationStore)

    >>> reg = mock.Mock()
    >>> reg.factory = NumbersStore
    >>> handler = enforce.FileSectionsEnforcerEventHandler(reg)

    Let's now dispatch events to see how the store get's called:

    1. File Creation:

    >>> evt = watchdog.events.FileCreatedEvent('./path/number:1.ini')
    >>> handler.dispatch(evt)
    True

    >>> NumbersStore.loadFromSection.assert_called_with(config, 'number:1')

    2. File Modification

    >>> NumbersStore.loadFromSection.reset_mock()
    >>> evt = watchdog.events.FileModifiedEvent('./path/number:1.ini')
    >>> handler.dispatch(evt)
    True

    >>> NumbersStore.loadFromSection.assert_called_with(config, 'number:1')

    3. File Deletion

    >>> store.reset_mock()
    >>> evt = watchdog.events.FileDeletedEvent('./path/number:1.ini')
    >>> handler.dispatch(evt)
    True

    >>> NumbersStore.deleteItem.assert_called_with('1')

    If no store is found, we simply return and do nothing:

    >>> NumbersStore.loadFromSection.reset_mock()
    >>> evt = watchdog.events.FileCreatedEvent('./path/int:1.ini')
    >>> handler.dispatch(evt)
    False

    >>> NumbersStore.loadFromSection.called
    False

    """


def doctest_SeparateFileEnforcerEventHandler():
    """Separate File Enforcer Event Handler

    >>> config = mock.Mock()

    >>> class NumbersStore(enforce.EnforcerFileSectionsCollectionStore):
    ...     section = 'numbers'
    ...     section_prefix = 'number:'
    ...
    ...     @classmethod
    ...     def fromRootAndFilename(cls, root, filename=None):
    ...         return cls()
    ...
    ...     _createConfigParser = mock.Mock(return_value=config)
    ...     load = mock.Mock()
    ...     deleteItem = mock.Mock()

    >>> zope.component.provideAdapter(
    ...     NumbersStore, (zope.interface.Interface,),
    ...     interfaces.IConfigurationStore)

    >>> reg = mock.Mock()
    >>> reg.factory = NumbersStore
    >>> handler = enforce.SeparateFileEnforcerEventHandler(reg)

    Let's now dispatch events to see how the store get's called:

    1. File Creation:

    >>> evt = watchdog.events.FileCreatedEvent('./path/number:1.ini')
    >>> handler.dispatch(evt)
    True

    >>> NumbersStore.load.assert_called_with(config)

    2. File Modification

    >>> NumbersStore.load.reset_mock()
    >>> evt = watchdog.events.FileModifiedEvent('./path/number:1.ini')
    >>> handler.dispatch(evt)
    True

    >>> NumbersStore.load.assert_called_with(config)

    3. File Deletion - Error is logged, since deleting those files amkes no
       sense.

    >>> evt = watchdog.events.FileDeletedEvent('./path/number:1.ini')
    >>> handler.dispatch(evt)
    True

    If no store is found, we simply return and do nothing:

    >>> NumbersStore.load.reset_mock()
    >>> evt = watchdog.events.FileCreatedEvent('./path/int:1.ini')
    >>> handler.dispatch(evt)
    False

    >>> NumbersStore.load.called
    False

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
    return doctest.DocTestSuite(
        setUp=setUp, tearDown=tearDown, optionflags=optionflags)
