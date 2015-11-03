###############################################################################
#
# Copyright 2015 by Shoobx, Inc.
#
###############################################################################
"""Module implementing a file listener to config changes.
"""
import logging
import os
import time
import watchdog.events
import watchdog.observers
import zope.component
import zope.interface

from z3c.insist import interfaces

logger = logging.getLogger('z3c.insist.enforcer')

@zope.interface.implementer(interfaces.IConfigurationStoreEventHandler)
@zope.component.adapter(zope.interface.Interface)
class FileSectionsCollectionConfigurationStoreEventHandler(
        watchdog.events.PatternMatchingEventHandler):
    storeFactory = None

    def __init__(self, context):
        self.context = context
        super(FileSectionsCollectionConfigurationStoreEventHandler, self)\
          .__init__(
            patterns=self.getFilePatterns(),
            ignore_patterns=['*/.#*.*'])

    def getFilePatterns(self):
        return ['*/%s*.*' % self.storeFactory.section_prefix]

    def getSectionFromFilename(self, filename):
        # Limitation. Assume that the section does not have any "." in it.
        return filename.split('.', 1)[0]

    def createStore(self, section):
        raise NotImplemented()

    def on_modified(self, event):
        filename = os.path.split(event.src_path)[-1]
        logger.info('File modified: %s (%s)', filename, self.__class__.__name__)
        ts = time.time()
        section = self.getSectionFromFilename(filename)
        store = self.createStore(section)
        config = store._createConfigParser()
        store.loadFromSection(config, section)
        logger.debug('Event completed in %.1fms.', (time.time()-ts)*1000)

    def on_created(self, event):
        filename = os.path.split(event.src_path)[-1]
        logger.info('File created: %s (%s)', filename, self.__class__.__name__)
        ts = time.time()
        section = self.getSectionFromFilename(filename)
        store = self.createStore(section)
        config = store._createConfigParser()
        store.loadFromSection(config, section)
        logger.debug('Event completed in %.1fms.', (time.time()-ts)*1000)

    def on_deleted(self, event):
        filename = os.path.split(event.src_path)[-1]
        logger.info('File deleted: %s (%s)', filename, self.__class__.__name__)
        ts = time.time()
        section = self.getSectionFromFilename(filename)
        store = self.createStore(section)
        name = section.replace(store.section_prefix, '')
        store.deleteItem(name)
        logger.debug('Event completed in %.1fms.', (time.time()-ts)*1000)


class Enforcer(object):
    """Detects configuration changes and applies them."""

    def __init__(self, watched_dir, context):
        self.observer = watchdog.observers.Observer()
        self.watchedDir = watched_dir
        self.context = context

    def register(self, factory):
        self.observer.schedule(factory(self.context), path=self.watchedDir)

    def start(self):
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()


class EventHandlerSubscriberEnforcer(Enforcer):

    def start(self):
        for handler in zope.component.subscribers(
                (self.context,), interfaces.IConfigurationStoreEventHandler):
            logger.info(
                'Registering event handler: %s %r',
                handler.__class__.__name__, handler.getFilePatterns())
            self.observer.schedule(handler, path=self.watchedDir)
        super(EventHandlerSubscriberEnforcer, self).start()
