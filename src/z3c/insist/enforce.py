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
import watchdog.utils
import zope.component
import zope.interface
from pathtools.patterns import match_any_paths

from z3c.insist import interfaces

logger = logging.getLogger('z3c.insist.enforcer')


class EnforcerFileSectionsCollectionStore(object):

    @classmethod
    def fromRootAndFilename(cls, root, filename=None):
        raise NotImplementedError('Create store from root and filename.')

    def getFilePatterns(self):
        return ['*/%s.ini' % self.section,
                '*/%s*.*' % self.section_prefix]


class EnforcerEventHandler(watchdog.events.FileSystemEventHandler):
    ignore_patterns = [
        '*/.#*.*',  # Emacs temporary files
        ]
    case_sensitive = True

    def __init__(self, root):
        self.root = root
        self.setUp()

    def setUp(self):
        self.path2StoreCache = {}
        self.patternsToStoreFactoryMap = []
        gsm = zope.component.globalSiteManager
        for reg in gsm.registeredAdapters():
            if not reg.provided.isOrExtends(interfaces.IConfigurationStore):
                continue
            logger.debug('Found store: %r', reg.factory)
            if not hasattr(reg.factory, 'fromRootAndFilename'):
                continue
            patterns = reg.factory().getFilePatterns()
            logger.info(
                'Registering %r -> %s', patterns, reg.factory.__name__)
            self.patternsToStoreFactoryMap.append((patterns, reg.factory))

    def createStore(self, factory, path):
        return factory.fromRootAndFilename(self.root, path)

    def getStoreFromEvent(self, event):
        path = watchdog.utils.unicode_paths.decode(event.src_path)

        if path in self.path2StoreCache:
            factory = self.path2StoreCache[path]
            return self.createStore(factory, path)

        for patterns, factory in self.patternsToStoreFactoryMap:
            if match_any_paths([path],
                               included_patterns=patterns,
                               excluded_patterns=self.ignore_patterns,
                               case_sensitive=self.case_sensitive):
                return self.createStore(factory, path)

    def getSectionFromEvent(self, event):
        filename = os.path.split(event.src_path)[-1]
        return filename.split('.', 1)[0]

    def dispatch(self, event):
        ts = time.time()
        store = self.getStoreFromEvent(event)
        if store is None:
            return
        event.store = store
        event.section = self.getSectionFromEvent(event)
        super(EnforcerEventHandler, self).dispatch(event)
        logger.info('Configuration updated  in %.1fms.', (time.time()-ts)*1000)

    def on_modified(self, event):
        config = event.store._createConfigParser()
        event.store.loadFromSection(config, event.section)

    def on_created(self, event):
        config = event.store._createConfigParser()
        event.store.loadFromSection(config, event.section)

    def on_deleted(self, event):
        name = event.section.replace(event.store.section_prefix, '')
        event.store.deleteItem(name)


class Enforcer(watchdog.observers.Observer):
    """Detects configuration changes and applies them."""

    def __init__(self, watched_dir):
        self.watchedDir = watched_dir
        super(Enforcer, self).__init__()

    def register(self, handler):
        self.schedule(handler, path=self.watchedDir, recursive=True)
