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
        '*/.*~',     # Vim temporary files
        '*/*.swp',  # Vim temporary files
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
        return event.store.getSectionFromPath(event.src_path)

    def dispatch(self, event):
        ts = time.time()
        store = self.getStoreFromEvent(event)
        if store is None:
            return False
        event.store = store
        event.section = self.getSectionFromEvent(event)
        super(EnforcerEventHandler, self).dispatch(event)
        logger.info('Configuration for %r updated in %.1fms.',
                    store.root, (time.time()-ts)*1000)
        return True

    def on_modified(self, event):
        raise NotImplementedError()

    def on_created(self, event):
        raise NotImplementedError()

    def on_deleted(self, event):
        raise NotImplementedError()


class SimpleEnforcerEventHandler(EnforcerEventHandler):

    def on_modified(self, event):
        config = event.store._createConfigParser()
        with open(event.src_path, 'r') as fle:
            config.readfp(fle)
        event.store.load(config)

    def on_created(self, event):
        config = event.store._createConfigParser()
        with open(event.src_path, 'r') as fle:
            config.readfp(fle)
        event.store.load(config)

    def on_deleted(self, event):
        logger.error(
            'Collection files should not be deleted: %s', event.src_path)


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

    lockFilename = 'lock'

    handlers = {
        insist.FileSectionsCollectionConfigurationStore: \
            FileSectionsEnforcerEventHandler,
        insist.SeparateFileCollectionConfigurationStore: \
            SeparateFileEnforcerEventHandler
        }

    gsm = zope.component.globalSiteManager

    def __init__(self, watched_dir, context=None):
        self.watchedDir = watched_dir
        self.lockedDirectories = set()
        self.context = context
        self.path2HandlerCache = {}
        super(Enforcer, self).__init__()

    def _handleLocks(self, event):
        # The config directory can be locked by other processes. For that time
        # all event listening should be suspended. Unfortuantely, oftentimes
        # inotify events are not fired until the lock is released.
        # The good news is that inotify guarantees the file events to be
        # generated in order, so that we can use the lock file creation and
        # deletion events as markers.
        eventDir = os.path.dirname(event.src_path)
        lockPath = os.path.join(eventDir, self.lockFilename)

        # 1. Sometimes we start up without knowing about some locked
        #    directories, so let's make sure we are up-to-date.
        if os.path.exists(lockPath) and eventDir not in self.lockedDirectories:
                self.lockedDirectories.add(eventDir)

        # 2. If the event happened in a locked directory, we ignore the event.
        if event.src_path != lockPath and eventDir in self.lockedDirectories:
            logger.debug('Event ignored due to suspension: %r', event)
            return True

        # 3. If we are not dealing with a lock file, we are not handling this
        #    event.
        if not event.src_path.endswith(self.lockFilename):
            return False

        # 4. Now handle the various lock operations.
        # 4.1. Add the directory to the locked directories list if the
        #      lock file was created.
        if event.event_type == watchdog.events.EVENT_TYPE_CREATED:
            self.lockedDirectories.add(eventDir)
            logger.debug('Enforcer suspended due to directory locking.')
        # 4.2. Remove the directory from the locked directories list if the
        #      lock file was deleted.
        elif event.event_type == watchdog.events.EVENT_TYPE_DELETED:
            if eventDir in self.lockedDirectories:
                self.lockedDirectories.remove(eventDir)
            logger.debug('Enforcer resuming after directory unlocking.')

        return True

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
            # Optimization: Ignore all dorectory modified events, since we
            # cannot really do anything with those. It will also avoid
            # unnecessary transactions due to lock file action.
            if event.is_directory and \
                event.event_type == watchdog.events.EVENT_TYPE_MODIFIED:
                return True
            # Handle lock file events first.
            handled = self._handleLocks(event)
            if handled:
                return
            # Use simple cache from path to handler, which is specific to our
            # limited use of watchdog.
            path = event.src_path
            if path in self.path2HandlerCache:
                try:
                    self.path2HandlerCache[path].dispatch(event)
                except Exception as err:
                    # Handle all exceptions that happen whilel handling the
                    # event and continue.
                    logger.exception('Exception while handling event.')
                return
            # To allow unschedule/stop and safe removal of event handlers
            # within event handlers itself, check if the handler is still
            # registered after every dispatch.
            for handler in list(self._handlers.get(watch, [])):
                if handler in self._handlers.get(watch, []):
                    try:
                        handled = handler.dispatch(event)
                    except Exception as err:
                        # Handle all exceptions that happen whilel handling the
                        # event and continue.
                        logger.exception('Exception while handling event.')
                        handled = True
                    # Enforcer supports exactely one handler per file.
                    if handled:
                        self.path2HandlerCache[path] = handler
                        break
        event_queue.task_done()
