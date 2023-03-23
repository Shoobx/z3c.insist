###############################################################################
#
# Copyright 2015 by Shoobx, Inc.
#
###############################################################################
"""Module implementing a file listener to config changes.
"""
import collections
import dataclasses
import logging
import os
import pathlib
import re
import time
import watchdog.events
import watchdog.observers
import watchdog.utils
import zope.component
import zope.interface
from watchdog.utils.patterns import match_any_paths

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
        path = os.fsdecode(event.src_path)

        if match_any_paths([path],
                           included_patterns=self.patterns,
                           excluded_patterns=self.ignore_patterns,
                           case_sensitive=self.case_sensitive):
            return self.createStore(self.factory, path)

    def getSectionFromEvent(self, event):
        return event.store.getSectionFromPath(event.src_path)

    def dispatch(self, event):
        if event.event_type == watchdog.events.EVENT_TYPE_OPENED:
            # Do not update configuration for EVENT_TYPE_OPENED. Doing this to avoid
            # unnecessary processing on file open events, need this since watchdog
            # started sending EVENT_TYPE_OPENED events. Eventually refactor dispatch
            # and event handlers later to do work only on specific events.
            return False
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

    def dispatch_events(self, event_queue):
        event, watch = event_queue.get(block=True)

        with self._lock:
            # Optimization: Ignore all directory modified events, since we
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
                        # Handle all exceptions that happen while handling the
                        # event and continue.
                        logger.exception('Exception while handling event.')
                        handled = True
                    # Enforcer supports exactely one handler per file.
                    if handled:
                        self.path2HandlerCache[path] = handler
                        break
        event_queue.task_done()


class IncludingFilesHandler(watchdog.events.FileSystemEventHandler):
    """Including File Event Handler.

    This handler listens for changes to any watched config (`*.ini`) files to
    check whether any included files changed. If the `#include` statements in
    an config file change, then the `IncludeOserver` is updated appropriately.
    """
    patterns = ['*/*.ini']
    ignore_patterns = [
        '*/.#*.*',  # Emacs temporary files
        '*/.*~',     # Vim temporary files
        '*/*.swp',  # Vim temporary files
        ]
    case_sensitive = True

    def __init__(self, incObserver):
        self.incObserver = incObserver

    def dispatch(self, event):
        print('-'*78)
        print(event)
        if event.is_directory:
            return

        if match_any_paths([os.fsdecode(event.src_path)],
                           included_patterns=self.patterns,
                           excluded_patterns=self.ignore_patterns,
                           case_sensitive=self.case_sensitive):
            super().dispatch(event)

    def on_modified(self, event):
        self.incObserver.update(event.src_path)

    def on_created(self, event):
        self.incObserver.update(event.src_path)

    def on_deleted(self, event):
        self.incObserver.update(event.src_path)


class IncludedFilesHandler(watchdog.events.FileSystemEventHandler):
    """Included File Event Handler

    An event handler that tracks all included files and will touch to the
    including file upon changes. The touch will in return cause the proper
    handler for the including file to be called.

    This algorithm is not 100% fool proof as it would not listen to changes of
    involved non-config files.
    """

    def __init__(self, incObserver):
        self.incObserver = incObserver

    def dispatch(self, event):
        if pathlib.Path(event.src_path) not in self.incObserver.includedFiles:
            return
        super().dispatch(event)

    def on_modified(self, event):
        included = self.incObserver.includedFiles[pathlib.Path(event.src_path)]
        for filepath in included:
            # Touch the including file which will trigger the enforcer to run
            # the update handler.
            logger.info(
                f'Included file in "{filepath}" changed. '
                'Touch file to trigger update.')
            pathlib.Path(filepath).touch()

    def on_deleted(self, event):
        logger.error(
            'Included File cannot be deleted: %s', event.src_path)


class IncludeObserver(watchdog.observers.Observer):

    watchedDir: str

    # A mapping of included files to watched files.
    includedFiles: collections.defaultdict
    # A mapping of watched files to included files.
    watchedFiles: collections.defaultdict
    # A mapping of directories that contain include files to watched files
    # that reference the directory. This is needed to know when a directory
    # should be scheduled or unscheduled.
    includeDirs: collections.defaultdict
    # Watches for included directories.
    watches: dict

    EventHandler = IncludedFilesHandler

    def __init__(self, watchedDir: str, context=None):
        self.watchedDir = watchedDir
        self.includedFiles = collections.defaultdict(lambda: set())
        self.watchedFiles = collections.defaultdict(lambda: set())
        self.includeDirs = collections.defaultdict(lambda: set())
        self.watches = {}
        super().__init__()

    def initialize(self) -> None:
        logger.info(f'Initializing Include Observer for {self.watchedDir}')
        for path in pathlib.Path(self.watchedDir).rglob('*.ini'):
            self.update(path)
        self.schedule(
            IncludingFilesHandler(self),
            path=self.watchedDir, recursive=True)

    def update(
            self,
            watchedPath: str
    ) -> None:
        # Convert file path to proper Path object.
        path = pathlib.Path(watchedPath)
        # 1. Enumerate the included files. If the file does not exist, skip
        #    it. It is commonly due to the deletion of the ini file.
        includes = []
        if path.exists():
            with open(path, 'r') as fp:
                cfgstr = fp.read()
            includes = set([
                pathlib.Path(path.parent, include).resolve()
                for include in re.findall(
                        insist.RE_INCLUDES, cfgstr, re.MULTILINE)
            ])
        logger.debug(
            f'Updating include observer: {watchedPath} '
            f'includes {[str(inc) for inc in includes]}')

        # 2. Determine the added and removed include files by comparing the
        #    old and new lists.
        addedIncludes = includes - self.watchedFiles[path]
        removedIncludes = self.watchedFiles[path] - includes

        # 3. Update the state for each newly included file.
        for added in addedIncludes:
            # 3.1. Update the `includedFiles` index.
            self.includedFiles[added].add(path)
            # 3.2. Update the `includeDirs` state and schedule a "watch" for
            #      the directory if necessary, so we can pick up changes to
            #      the included file.
            addedDir = added.parent
            # 3.2.1. If this is the first time we see the included directory,
            #        schedule the event listener and record the watcher.
            if not self.includeDirs[addedDir]:
                logger.debug(
                    f'Start watching include dir: {addedDir}')
                self.watches[addedDir] = self.schedule(
                    self.EventHandler(self),
                    path=str(addedDir), recursive=False)
            # 3.2.2. Update the `includeDirs` state.
            self.includeDirs[addedDir].add(added)

        # 4. Update the state for each removed included file.
        for removed in removedIncludes:
            # 4.1. Update the `includedFiles` index.
            self.includedFiles[removed].remove(path)
            # 4.2. Update the `includeDirs` state and remove the "watch" for
            #      the directory if no more files require listening.
            removedDir = removed.parent
            # 4.2.1. Update the `includeDirs` state.
            self.includeDirs[removedDir].add(removed)
            # 4.2.2. If the last file in a directory was removed, then the
            #        watch for that directory can removed as well.
            if not self.includeDirs[removedDir]:
                logger.debug(
                    f'Stop watching include dir: {removedDir}')
                self.unschedule(self.watches[removedDir])
                del self.watches[removedDir]

        # 5. Update the `watchedFiles` state with the new list of includes.
        self.watchedFiles[path] = includes
