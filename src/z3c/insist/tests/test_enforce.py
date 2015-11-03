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

from z3c.insist import enforce, interfaces, testing


def doctest_Enforcer():
    r"""Base Enforcer Test

    We are using watchdog to listen for changed to the filesystem in a
    particular directory. The first argument is the target directory and the
    second one some context.

      >>> enf = enforce.Enforcer('./', {})

    Let's mock the actual watchdog observer, since we would need to start a
    thread to use it properly.

      >>> enf.observer = mock.Mock()
      >>> enf.observer.schedule = mock.Mock()

    To start with, we have to register at least one config store event handler.

      >>> TestHandler = mock.Mock()
      >>> enf.register(TestHandler)

      >>> TestHandler.assert_called_with({})
      >>> enf.observer.schedule.called
      True

    Now that we have a handler, we can start the enforcer.

      >>> enf.observer.start = mock.Mock()
      >>> enf.start()

      >>> enf.observer.start.called
      True

    At this point a thread would be started listening for inotify events. The
    thread can be shut down as follows:

      >>> enf.observer.stop = mock.Mock()
      >>> enf.stop()

      >>> enf.observer.stop.called
      True
    """

def doctest_EventHandlerSubscriberEnforcer():
    """Event Handler Subscriber Enforcer

    This is a component architecture driven enforcer that looks up the event
    handlers as subscribers to the context of the enforcer. Let me demonstrate.

    >>> TestHandler = mock.Mock()
    >>> zope.component.provideSubscriptionAdapter(
    ...     TestHandler,
    ...     adapts=(None,),
    ...     provides=interfaces.IConfigurationStoreEventHandler)

    >>> enf = enforce.EventHandlerSubscriberEnforcer('./', {})
    >>> enf.observer = mock.Mock()
    >>> enf.observer.schedule = mock.Mock()

    >>> enf.start()
    >>> TestHandler.called
    True
    >>> enf.observer.schedule.called
    True
    """

def doctest_FileSectionsCollectionConfigurationStoreEventHandler():
    """File Sections Collection Configuration Store Event Handler Test

    The file sections collection configuration store event handler is a
    watchdog event handler written to handle changes to config files
    controlled by file sections collection config stores. This event handler
    is meant as a base class that is implemented for each store.

    >>> config = mock.Mock()

    >>> store = mock.Mock()
    >>> store.section_prefix = 'number:'
    >>> store._createConfigParser = mock.Mock(return_value=config)
    >>> store.loadFromSection = mock.Mock()
    >>> store.deleteItem = mock.Mock()

    >>> class MyHandler(
    ...     enforce.FileSectionsCollectionConfigurationStoreEventHandler):
    ...     storeFactory = mock.Mock(section_prefix='number:')
    ...     createStore = mock.Mock(return_value=store)

    >>> handler = MyHandler({})

    There are some interesting hellper method that help identiying the files
    to listen for:

    >>> handler.patterns
    ['*/number:*.*']

    >>> handler.ignore_patterns
    ['*/.#*.*']

    >>> handler.getFilePatterns()
    ['*/number:*.*']

    Note that `getFilePatterns()` is called in the constructor to create the
    patterns attribute. If you need to cover more than the standard patterns,
    you should consider overwriting the `getFilePatterns()` method.

    There are also some methods that help identify the object name and config
    section:

    >>> handler.getSectionFromFilename('number:1.ini')
    'number:1'
    >>> handler.getSectionFromFilename('number:1.body.pt')
    'number:1'

    Let's now look at the watchdog event handler methods.

    1. File Creation:

    >>> store.reset_mock()
    >>> evt = watchdog.events.FileCreatedEvent('./path/number:1.ini')
    >>> handler.on_created(evt)

    >>> store._createConfigParser.called
    True
    >>> store.loadFromSection.assert_called_with(config, 'number:1')

    2. File Modification

    >>> store.reset_mock()
    >>> evt = watchdog.events.FileModifiedEvent('./path/number:1.ini')
    >>> handler.on_modified(evt)

    >>> store._createConfigParser.called
    True
    >>> store.loadFromSection.assert_called_with(config, 'number:1')

    3. File Deletion

    >>> store.reset_mock()
    >>> evt = watchdog.events.FileDeletedEvent('./path/number:1.ini')
    >>> handler.on_deleted(evt)

    >>> store.deleteItem.assert_called_with('1')
    """

def doctest_SeparateFileCollectionConfigurationStoreEventHandler():
    """SeparateFile Collection Configuration Store Event Handler Test

    The separate file collection configuration store event handler is a
    watchdog event handler written to handle changes to config files that
    contain their entire config in a single file. This event handler
    is meant as a base class that is implemented for each store.

    >>> config = mock.Mock()

    >>> store = mock.Mock()
    >>> store.section = 'numbers'
    >>> store.section_prefix = 'number:'
    >>> store._createConfigParser = mock.Mock(return_value=config)
    >>> store.loadFromSection = mock.Mock()
    >>> store.deleteItem = mock.Mock()

    >>> class MyHandler(
    ...     enforce.SeparateFileCollectionConfigurationStoreEventHandler):
    ...     storeFactory = mock.Mock(
    ...         section_prefix='number:', section='numbers')
    ...     createStore = mock.Mock(return_value=store)

    >>> handler = MyHandler({})

    There are some interesting hellper method that help identiying the files
    to listen for:

    >>> handler.patterns
    ['*/numbers.ini', '*/number:*.*']

    >>> handler.ignore_patterns
    ['*/.#*.*']

    >>> handler.getFilePatterns()
    ['*/numbers.ini', '*/number:*.*']

    Note that `getFilePatterns()` is called in the constructor to create the
    patterns attribute. If you need to cover more than the standard patterns,
    you should consider overwriting the `getFilePatterns()` method.

    There are also some methods that help identify the object name and config
    section:

    >>> handler.getSectionFromFilename('numbers.ini')
    'numbers'

    Let's now look at the watchdog event handler methods.

    1. File Creation:

    >>> store.reset_mock()
    >>> evt = watchdog.events.FileCreatedEvent('./path/numbers.ini')
    >>> handler.on_created(evt)

    >>> store._createConfigParser.called
    True
    >>> store.load.assert_called_with(config)

    2. File Modification

    >>> store.reset_mock()
    >>> evt = watchdog.events.FileModifiedEvent('./path/numbers.ini')
    >>> handler.on_modified(evt)

    >>> store._createConfigParser.called
    True
    >>> store.load.assert_called_with(config)

    3. File Deletion

    >>> store.reset_mock()
    >>> evt = watchdog.events.FileDeletedEvent('./path/numbers.ini')
    >>> handler.on_deleted(evt)

    >>> store._createConfigParser.called
    True
    >>> store.load.assert_called_with(config)
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
