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

from z3c.insist import interfaces, insist

logger = logging.getLogger('z3c.insist.enforcer')


class EnforcerFileSectionsCollectionStore(object):

    @classmethod
    def fromRootAndFilename(cls, root, filename=None):
        raise NotImplementedError('Create store from root and filename.')

    def getFilePatterns(self):
        return ['*/%s.ini' % self.section,
                '*/%s*.*' % self.section_prefix]


class EnforcerEventHandler(watchdog.events.FileSystemEventHandler):
    patterns = None
    ignore_patterns = [
        '*/.#*.*',  # Emacs temporary files
        ]
    case_sensitive = True

    def __init__(self, reg, root=None):
        self.root = root
        self.factory = reg.factory
        self.patterns = reg.factory().getFilePatterns()

    def createStore(self, factory, path):
        return factory.fromRootAndFilename(self.root, path)

    def getStoreFromEvent(self, event):
        path = watchdog.utils.unicode_paths.decode(event.src_path)

        if match_any_paths([path],
                           included_patterns=self.patterns,
                           excluded_patterns=self.ignore_patterns,
                           case_sensitive=self.case_sensitive):
            return self.createStore(self.factory, path)

    def getSectionFromEvent(self, event):
        filename = os.path.split(event.src_path)[-1]
        return filename.split('.', 1)[0]

    def dispatch(self, event):
        ts = time.time()
        store = self.getStoreFromEvent(event)
        if store is None:
            return False
        event.store = store
        event.section = self.getSectionFromEvent(event)
        super(EnforcerEventHandler, self).dispatch(event)
        logger.info('Configuration updated  in %.1fms.', (time.time()-ts)*1000)
        return True

    def on_modified(self, event):
        raise NotImplementedError()

    def on_created(self, event):
        raise NotImplementedError()

    def on_deleted(self, event):
        raise NotImplementedError()


class FileSectionsEnforcerEventHandler(EnforcerEventHandler):

    def on_modified(self, event):
        config = event.store._createConfigParser()
        event.store.loadFromSection(config, event.section)

    def on_created(self, event):
        config = event.store._createConfigParser()
        event.store.loadFromSection(config, event.section)

    def on_deleted(self, event):
        name = event.section.replace(event.store.section_prefix, '')
        event.store.deleteItem(name)


class SeparateFileEnforcerEventHandler(EnforcerEventHandler):

    def on_modified(self, event):
        config = event.store._createConfigParser()
        event.store.load(config)

    def on_created(self, event):
        config = event.store._createConfigParser()
        event.store.load(config)

    def on_deleted(self, event):
        logger.error(
            'Collection files should not be deleted: %s', event.src_path)


class Enforcer(watchdog.observers.Observer):
    """Detects configuration changes and applies them."""

    handlers = {
        insist.FileSectionsCollectionConfigurationStore: \
            FileSectionsEnforcerEventHandler,
        insist.SeparateFileCollectionConfigurationStore: \
            SeparateFileEnforcerEventHandler
        }

    gsm = zope.component.globalSiteManager

    def __init__(self, watched_dir, context=None):
        self.watchedDir = watched_dir
        self.context = context
        self.path2HandlerCache = {}
        super(Enforcer, self).__init__()

    def getEventHandlerForRegistration(self, reg):
        bases = reg.factory.__mro__
        for storeBase, handlerFactory in self.handlers.items():
            if storeBase in bases:
                return handlerFactory(reg, self.context)
        raise RuntimeError(
            'Could not find event handler for registration: %r',
            reg.factory)

    def registerHandlers(self):
        for reg in self.gsm.registeredAdapters():
            if not reg.provided.isOrExtends(interfaces.IConfigurationStore):
                continue
            logger.debug('Found store: %r', reg.factory)
            if not hasattr(reg.factory, 'fromRootAndFilename'):
                continue
            handler = self.getEventHandlerForRegistration(reg)
            logger.info(
                'Registering %r -> %s (%s)',
                handler.patterns, handler.factory.__name__,
                handler.__class__.__name__)
            self.register(handler)

    def register(self, handler):
        self.schedule(handler, path=self.watchedDir, recursive=True)

    def dispatch_events(self, event_queue, timeout):
        event, watch = event_queue.get(block=True, timeout=timeout)

        with self._lock:
            # Use simple cache from path to handler, which is specific to our
            # limited use of watchdog.
            path = event.src_path
            if path in self.path2HandlerCache:
                self.path2HandlerCache[path].dispatch(event)
                return
            # To allow unschedule/stop and safe removal of event handlers
            # within event handlers itself, check if the handler is still
            # registered after every dispatch.
            for handler in list(self._handlers.get(watch, [])):
                if handler in self._handlers.get(watch, []):
                    handled = handler.dispatch(event)
                    # Enforcer supports exactely one handler per file.
                    if handled:
                        self.path2HandlerCache[path] = handler
                        break
        event_queue.task_done()
