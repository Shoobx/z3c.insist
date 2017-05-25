###############################################################################
#
# Copyright 2013-15 by Shoobx, Inc.
#
###############################################################################
"""z3c.insist -- Persistence to ini files
"""
import configparser
import datetime
import decimal
import glob
import hashlib
import io
import iso8601
import json
import logging
import os
import sys
import zope.component
import zope.schema
from zope.schema import vocabulary


from z3c.insist import interfaces

PY3 = sys.version_info.major >= 3

if PY3:
    unicode = str
    from io import StringIO
else:
    from cStringIO import StringIO


class FilesystemMixin(object):
    """Hooks to abstract file access."""

    def listDir(self, path):
        return os.listdir(path)

    def fileExists(self, path):
        return os.path.exists(path)

    def getFileModTime(self, path):
        if not self.fileExists(path):
            return None
        return os.path.getmtime(path)

    def openFile(self, path, mode='r', encoding=None):
        return io.open(path, mode, encoding=encoding)

    def hashFile(self, filename):
        with self.openFile(filename, 'rb') as f:
            hsh = hashlib.sha256(f.read())
        return hsh.hexdigest()

    def hashFilesByPattern(self, pattern):
        """Return hash of all the files, specified in the glob pattern"""
        files = glob.glob(pattern)
        filehashes =[self.hashFile(fn) for fn in files]
        return hash(tuple(filehashes))


log = logging.getLogger(__name__)


@zope.interface.implementer(interfaces.IConfigurationStore)
class ConfigurationStore(object):
    """Base Configuration Store"""
    file_header = None
    _section = None
    fields = None
    ignore_fields = None
    ignore_missing = False
    ignore_default = False
    root = None

    def __init__(self, context=None):
        self.context = context

    @property
    def section(self):
        if self._section is None:
            return self.schema.__name__
        else:
            return self._section

    @section.setter
    def section(self, value):
        self._section = value

    def getSectionFromPath(self, path):
        return self.section

    @classmethod
    def makeStore(cls, value, schema, section=None):
        store = cls(value)
        store.schema = schema
        if section is not None:
            store.section = section
        return store

    def write(self, config, fileobj):
        if self.file_header is not None:
            fileobj.write(self.file_header + '\n')
        config.write(fileobj)

    def _createConfigParser(self, config=None):
        if config is None:
            config = configparser.RawConfigParser()
            config.optionxform = str
        return config

    def _get_fields(self):
        """Returns a sequence of (name, field) pairs"""
        return zope.schema.getFieldsInOrder(self.schema)

    def _dump(self, config, add_section=True):
        """Hook for extending"""
        if add_section:
            config.add_section(self.section)
        for fn, field in self._get_fields():
            if self.fields is not None and fn not in self.fields:
                continue
            if self.ignore_fields is not None and fn in self.ignore_fields:
                continue
            ftype = field.__class__.__name__
            __traceback_info__ = (self.section, self.schema, fn, ftype)
            if hasattr(self, 'dump_%s' % fn):
                serializer = CustomSerializer(field, self.context, self)
            elif hasattr(self, 'dump_type_%s' % ftype):
                serializer = CustomFieldTypeSerializer(field, self.context, self)
            else:
                serializer = zope.component.getMultiAdapter(
                    (field, self.context), interfaces.IFieldSerializer)
            if self.ignore_missing and not serializer.hasValue():
                continue
            state = serializer.serialize(self.ignore_default)
            # Give the serializer the opportunity to decide not to provide a
            # serialized value.
            if state is None:
                continue
            config.set(self.section, fn, state)

    def dump(self, config=None):
        config = self._createConfigParser(config)
        self._dump(config)
        return config

    def dumps(self):
        config = self.dump()
        buf = StringIO()
        self.write(config, buf)
        return buf.getvalue()

    def load(self, config):
        for fn, field in self._get_fields():
            if self.fields is not None and fn not in self.fields:
                continue
            # XXX: __name__ is special for RawConfigParser
            #      http://bugs.python.org/msg215809
            if not config.has_section(self.section):
                continue
            elif fn not in config.options(self.section):
                continue
            #if not config.has_option(self.section, fn):
            #    continue
            ftype = field.__class__.__name__
            __traceback_info__ = (self.section, self.schema, fn, ftype)
            if hasattr(self, 'load_%s' % fn):
                serializer = CustomSerializer(field, self.context, self)
            elif hasattr(self, 'load_type_%s' % ftype):
                serializer = CustomFieldTypeSerializer(field, self.context, self)
            else:
                serializer = zope.component.getMultiAdapter(
                    (field, self.context), interfaces.IFieldSerializer)
            serializer.deserialize(config.get(self.section, fn))
        zope.event.notify(
            interfaces.ObjectConfigurationLoadedEvent(
                self.context))

    def loads(self, cfgstr):
        config = self._createConfigParser()
        # Mostly ensure for Py2 that we actually pass in a unicode string.
        config.read_string(unicode(cfgstr))
        self.load(config)

class CollectionConfigurationStore(ConfigurationStore):
    """A configuration store for collections.

    Subclasses must provide the following attributes:

       * schema
       * section_prefix
       * item_factory

    Optionally:

       * item_factory_typed(config, section)
    """

    schema = None

    # Flag, indicating that this configuration store can properly support
    # syncing without reloading all objects. To support syncing store has to
    # implement `getConfigHash` method. Change in the hash indicates that child
    # has to be reloaded.
    supports_sync = True

    _deleted = 0
    _added = 0
    _reloaded = 0

    def selectSections(self, sections):
        """Return relevant sections from config
        """
        return (sec for sec in sections
                if sec.startswith(self.section_prefix))

    def getItemName(self, config, section):
        """Return a unique name for item, represented by this section
        """
        return section[len(self.section_prefix):]

    def addItem(self, name, obj):
        self._added += 1
        self.context[name] = obj

    def deleteItem(self, name):
        self._deleted += 1
        del self.context[name]

    def _createItemConfigStore(self, obj, config, section):
        store = interfaces.IConfigurationStore(obj)
        store.section = section
        store.root = self.root
        return store

    def dump(self, config=None):
        config = self._createConfigParser(config)
        for k, v in self.context.items():
            __traceback_info__ = (k, v)
            store = self._createItemConfigStore(
                v, config, self.section_prefix + k)
            store.dump(config)
        return config

    def load(self, config):
        self._deleted = 0
        self._added = 0
        self._reloaded = 0

        if not self.supports_sync:
            # No sync support, just delete all the items
            for k in self.context.keys():
                self.deleteItem(k)

        unloaded = set(self.context.keys())
        for section in self.selectSections(config.sections()):
            loaded = self.loadFromSection(config, section)
            if loaded in unloaded:
                unloaded.remove(loaded)

        # Remove any unloaded items from collection
        for k in unloaded:
            self.deleteItem(k)

        self._logStatus()

    def _logStatus(self):
        if not self.supports_sync:
            return

        if not self._deleted and not self._added and not self._reloaded:
            return

        log.info("Insist collection loading status for '%s': "
                 "%s reloaded, %s added, %s deleted",
                 self.schema,
                 self._reloaded, self._added, self._deleted)

    def _createNewItem(self, config, section):
        if hasattr(self, 'item_factory_typed'):
            obj = self.item_factory_typed(config, section)
        else:
            obj = self.item_factory()
        return obj

    def getSectionHash(self, config, section):
        return hash(tuple(config.items(section)))

    def getChildConfigHash(self, obj, config, section):
        return self.getSectionHash(config, section)

    def loadFromSection(self, config, section):
        """Load object from section and return name of the loaded object

        After this function is completed, object with returned name should
        exist in a collection and objects data should be up to date with
        configuration.
        """
        name = self.getItemName(config, section)

        existing = name in self.context
        # Obtain the object we are loading. Find in collection or create new
        # one.
        if existing:
            obj = self.context[name]
        else:
            obj = self._createNewItem(config, section)

        # Find the store object, that will handle loading
        confhash = self.getChildConfigHash(obj, config, section)

        # Check if configuration has changed. Note that in some cases when the
        # object is new, the hash might not have been computable and thus
        # None. In those cases we want to go on.
        if confhash is not None and \
          getattr(obj, "__insist_hash__", None) == confhash:
            return name

        # Config has changed, we can load object with properties from
        # configuration.

        if existing:
            self._reloaded += 1

        # First of all, make sure class of the item didn't change. Otherwise we
        # have to remove it and re-add, because property set for it may be
        # completely different.
        if existing:
            newobj = self._createNewItem(config, section)
            if newobj.__class__ is not obj.__class__:
                # Yeah, class have changed, let's replace the item
                self.deleteItem(name)
                obj = newobj
                existing = False

        # Now we can load properties into the object
        store = self._createItemConfigStore(obj, config, section)
        store.load(config)
        # Set the confhash.
        obj.__insist_hash__ = confhash

        if not existing:
            # Let everyone know the object is being added to a collection
            if hasattr(store, 'loadBeforeAdd'):
                obj = store.loadBeforeAdd(name, config)
            self.addItem(name, obj)
            if hasattr(store, 'loadAfterAdd'):
                store.loadAfterAdd(config)

        return name


@zope.interface.implementer(interfaces.ISeparateFileConfigurationStore)
class SeparateFileConfigurationStoreMixIn(FilesystemMixin):
    allowMainConfigLoad = True
    dumpSectionStub = True
    subConfig = None

    def getConfigPath(self):
        raise NotImplemented

    def getConfigFilename(self):
        return self.section + '.ini'

    def _dumpSubConfig(self, config):
        super(SeparateFileConfigurationStoreMixIn, self).dump(config)

    def dump(self, config=None):
        # 1. Store all items in a separate configuration file.
        # 1.1. Create the config object and fill it.
        subconfig = self._createConfigParser()
        self._dumpSubConfig(subconfig)
        # 1.2. Dump the config in a file.
        configFilename = self.getConfigFilename()
        configPath = os.path.join(self.getConfigPath(), configFilename)
        with self.openFile(configPath, 'w') as file:
            self.write(subconfig, file)

        # 2. Store a reference to the cofniguration file in the main
        #    configuration object.
        # 2.1. Create the config object, if it does not exist.
        config = self._createConfigParser(config)
        # 2.2. Now dump the section stub in the original config object, if so
        #      desired.
        if self.dumpSectionStub:
            config.add_section(self.section)
            config.set(self.section, 'config-file', configFilename)

        return config

    def _loadSubConfig(self, config):
        super(SeparateFileConfigurationStoreMixIn, self).load(config)

    def load(self, config):
        # 1. Generate the config file path.
        configFilename = self.getConfigFilename()
        configPath = os.path.join(self.getConfigPath(), configFilename)

        # 2. Create a new sub-config object and load the data.
        if self.subConfig is not None:
            pass
        elif not self.fileExists(configPath):
            if not self.allowMainConfigLoad:
                raise ValueError(
                    'Configuration file does not exist: %s' % configPath)
            # Assume that the configuration is part of the main config. This
            # allows for controlled migration.
            self.subConfig = config
        else:
            self.subConfig = self._createConfigParser()
            with self.openFile(configPath, 'r') as fle:
                self.subConfig.readfp(fle)
        # 3. Load as usual from the sub-config.
        self._loadSubConfig(self.subConfig)


class SeparateFileConfigurationStore(
        SeparateFileConfigurationStoreMixIn, ConfigurationStore):
    pass


class SeparateFileCollectionConfigurationStore(
        SeparateFileConfigurationStoreMixIn, CollectionConfigurationStore):

    def getChildConfigHash(self, obj, config, section):
        ownhash = super(SeparateFileCollectionConfigurationStore, self). \
            getChildConfigHash(obj, config, section)
        # With making the assumption that all object related config files
        # start with section name + ".", we simply create the hash from the
        # mod time of all files found.
        configPath = self.getConfigPath()
        pattern = os.path.join(configPath, "%s.*" % section)
        fileshash = self.hashFilesByPattern(pattern)
        return hash((ownhash, fileshash))


class FileSectionsCollectionConfigurationStore(
        CollectionConfigurationStore, FilesystemMixin):
    """File Section Configuration Store

    These are collection stores that look for sections in other files. A base
    implementation is provided that assumes that the filenames and section
    names are identical.
    """
    allowMainConfigLoad = True
    filePostfix = '.ini'

    def __init__(self, *args, **kw):
        super(FileSectionsCollectionConfigurationStore, self).__init__(
            *args, **kw)
        # A cache, so that we need to read each config file at most once.
        self.section_configs = {}

    def _createItemConfigStore(self, obj, config, section):
        store = super(FileSectionsCollectionConfigurationStore, self)\
          ._createItemConfigStore(obj, config, section)
        store.subConfig = self.section_configs.get(section)
        return store

    def getConfigPath(self):
        raise NotImplementedError

    def getSectionPath(self, section):
        return os.path.join(self.getConfigPath(), section + self.filePostfix)

    def getSectionFromPath(self, path):
        dirname, section_name = os.path.split(path)
        while '.' in section_name:
            section_name = section_name.rsplit('.', 1)[0]
            if self.fileExists(self.getSectionPath(section_name)):
                return section_name
        raise RuntimeError(
            'Could not find valid section name in path: %s' % path)

    def selectSections(self, sections):
        baseDir = self.getConfigPath()
        file_sections = [
            filename[:-len(self.filePostfix)]
            for filename in self.listDir(baseDir)
            if (filename.startswith(self.section_prefix) and
                filename.endswith(self.filePostfix))]
        if file_sections:
            return file_sections
        # If we allow loading via main config file, let's use the usual way to
        # lookup sections.
        if not self.allowMainConfigLoad:
            return []
        return super(FileSectionsCollectionConfigurationStore, self)\
          .selectSections(sections)

    def getConfigForSection(self, section):
        if section not in self.section_configs:
            config = self._createConfigParser()
            with self.openFile(self.getSectionPath(section), 'r') as file:
                config.readfp(file)
            self.section_configs[section] = config
        return self.section_configs[section]

    def getChildConfigHash(self, obj, config, section):
        # With making the assumption that all object related config files
        # start with section name + ".", we simply create the hash from the
        # mod time of all files found.
        configPath = self.getConfigPath()
        pattern = os.path.join(configPath, "%s.*" % section)
        return self.hashFilesByPattern(pattern)


@zope.interface.implementer(interfaces.IFieldSerializer)
class FieldSerializer(object):
    escape = '!'

    def __init__(self, field, context):
        self.field = field
        self.context = context

    def hasValue(self):
        value = getattr(self.context, self.field.__name__)
        return value is not self.field.missing_value

    def serializeValueWithNone(self, value):
        if value is None:
            return interfaces.NONE_MARKER
        else:
            result = self.serializeValue(value)
            if result is None:
                return None
            return result.replace(self.escape, self.escape * 2)

    def serialize(self, ignoreDefault=False):
        value = getattr(self.context, self.field.__name__)
        if ignoreDefault and value == self.field.default:
            return None
        return self.serializeValueWithNone(value)

    def deserializeValueWithNone(self, value):
        if value == interfaces.NONE_MARKER:
            return None
        else:
            value = value.replace(self.escape * 2, self.escape)
            return self.deserializeValue(value)

    def deserialize(self, value):
        setattr(self.context, self.field.__name__,
                self.deserializeValueWithNone(value))


@zope.component.adapter(
    zope.schema.interfaces.IBytes, zope.interface.Interface)
class BytesFieldSerializer(FieldSerializer):
    def serializeValue(self, value):
        return value.decode('utf-8')

    def deserializeValue(self, value):
        return value.encode('utf-8')


@zope.component.adapter(
    zope.schema.interfaces.IText, zope.interface.Interface)
class TextFieldSerializer(FieldSerializer):
    def serializeValue(self, value):
        return value

    def deserializeValue(self, value):
        return value


@zope.component.adapter(
    zope.schema.interfaces.ITextLine, zope.interface.Interface)
class TextLineFieldSerializer(TextFieldSerializer):
    pass


@zope.component.adapter(
    zope.schema.interfaces.IInt, zope.interface.Interface)
class IntFieldSerializer(FieldSerializer):
    def serializeValue(self, value):
        return str(value)

    def deserializeValue(self, value):
        return int(value)


@zope.component.adapter(
    zope.schema.interfaces.IFloat, zope.interface.Interface)
class FloatFieldSerializer(FieldSerializer):
    def serializeValue(self, value):
        return str(value)

    def deserializeValue(self, value):
        return float(value)


@zope.component.adapter(
    zope.schema.interfaces.IDecimal, zope.interface.Interface)
class DecimalFieldSerializer(FieldSerializer):
    def serializeValue(self, value):
        return str(value)

    def deserializeValue(self, value):
        return decimal.Decimal(value)


@zope.component.adapter(
    zope.schema.interfaces.IBool, zope.interface.Interface)
class BoolFieldSerializer(FieldSerializer):
    def serializeValue(self, value):
        return str(value)

    def deserializeValue(self, value):
        return value in ('True', 'true')


@zope.component.adapter(
    zope.schema.interfaces.IDate, zope.interface.Interface)
class DateFieldSerializer(FieldSerializer):
    format = '%Y-%m-%d'

    def serializeValue(self, value):
        return value.strftime(self.format)

    def deserializeValue(self, value):
        return datetime.datetime.strptime(value, self.format).date()


@zope.component.adapter(
    zope.schema.interfaces.IDatetime, zope.interface.Interface)
class DateTimeFieldSerializer(FieldSerializer):
    # format = '%Y-%m-%dT%H:%M:%S.%f+%z'
    # notzFormat = '%Y-%m-%dT%H:%M:%S.%f'

    def serializeValue(self, value):
        return value.isoformat()

    def deserializeValue(self, value):
        # the pain here is that datetimes without a TZ burp with
        # ValueError: time data '2014-01-01T00:00:00.000000'
        #   does not match format '%Y-%m-%dT%H:%M:%S.%f %Z'
        # and strptime isn't tops with timezones (does not support %z)
        #return dateutil.parser.parse(value)

        return iso8601.parse_date(value)


@zope.component.adapter(
    zope.schema.interfaces.IChoice, zope.interface.Interface)
class ChoiceFieldSerializer(FieldSerializer):

    def _getVocabulary(self):
        vocab = self.field.vocabulary
        if vocab is None:
            reg = vocabulary.getVocabularyRegistry()
            vocab = reg.get(self.context, self.field.vocabularyName)
        return vocab

    def serializeValue(self, value):
        vocabulary = self._getVocabulary()
        try:
            return vocabulary.getTerm(value).token
        except LookupError:
            # The term does not exist any more. Since in most cases the for
            # user-defined vocabularies the value == token, we'll just return
            # the str'ed value.
            return str(value)

    def deserializeValue(self, value):
        vocabulary = self._getVocabulary()
        try:
            return vocabulary.getTermByToken(value).value
        except LookupError:
            # The term does not exist any more. Since in most cases the for
            # user-defined vocabularies the value == token, we'll just return
            # the str'ed value.
            return unicode(value)


class SequenceFieldSerializer(FieldSerializer):

    sequence = None
    separator = ", "
    __item_serializer = None

    @property
    def _item_serializer(self):
        if self.__item_serializer is None:
            self.__item_serializer = zope.component.getMultiAdapter(
            (self.field.value_type, self.context), interfaces.IFieldSerializer)
        return self.__item_serializer

    def serializeValue(self, value):
        results = []
        for item in value:
            results.append(self._item_serializer.serializeValueWithNone(item))
        return self.separator.join(results)

    def deserializeValue(self, value):
        if value == '':
            return self.sequence()
        results = []
        for item in value.split(self.separator):
            __traceback_info__ = item, self.field.value_type
            item = item.strip()
            results.append(self._item_serializer.deserializeValueWithNone(item))
        return self.sequence(results)


@zope.component.adapter(zope.schema.interfaces.IList, zope.interface.Interface)
class ListFieldSerializer(SequenceFieldSerializer):
    sequence = list


@zope.component.adapter(zope.schema.interfaces.ITuple, zope.interface.Interface)
class TupleFieldSerializer(SequenceFieldSerializer):
    sequence = tuple


class CustomSerializer(FieldSerializer):
    """Allow a field-specific method on storage handle the value.

    Expects that the store will have methods `dump_foo` and `load_foo`
    that do the value conversion for field `foo`.
    """
    def __init__(self, field, context, store):
        self.field = field
        self.context = context
        self.store = store

    def serializeValue(self, value):
        return getattr(self.store, 'dump_' + self.field.__name__)(value)

    def deserializeValue(self, value):
        return getattr(self.store, 'load_' + self.field.__name__)(value)


class CustomFieldTypeSerializer(FieldSerializer):
    """Allow a field-specific method on storage handle the value.

    Expects that the store will have methods `dump_foo` and `load_foo`
    that do the value conversion for field `foo`.
    """
    def __init__(self, field, context, store):
        self.field = field
        self.ftype = field.__class__.__name__
        self.context = context
        self.store = store

    def serializeValue(self, value):
        return getattr(self.store, 'dump_type_' + self.ftype)(self.field, value)

    def deserializeValue(self, value):
        return getattr(self.store, 'load_type_' + self.ftype)(self.field, value)


@zope.component.adapter(zope.schema.interfaces.IDict, zope.interface.Interface)
class DictFieldSerializer(FieldSerializer):

    factory = dict
    separator = '::'
    __key_serializer = None
    __value_serializer = None

    @property
    def _key_serializer(self):
        if self.__key_serializer is None:
            self.__key_serializer = zope.component.getMultiAdapter(
            (self.field.key_type, self.context), interfaces.IFieldSerializer)
        return self.__key_serializer

    @property
    def _value_serializer(self):
        if self.__value_serializer is None:
            self.__value_serializer = zope.component.getMultiAdapter(
            (self.field.value_type, self.context), interfaces.IFieldSerializer)
        return self.__value_serializer

    def _encodeString(self, value):
        # drive string through json, to encode eventual \n and stuff
        return json.dumps(value)[1:-1]

    def _decodeString(self, value):
        # drive string through json, to decode eventual \n and stuff
        return json.loads('"' + value + '"')

    def serializeValue(self, value):
        results = []
        # serialize key and values with their serializers
        # supports OrderedDict too, just need to override self.factory
        for key, val in value.items():
            keySer = self._key_serializer.serializeValueWithNone(key)
            keySer = self._encodeString(keySer)
            valSer = self._value_serializer.serializeValueWithNone(val)
            valSer = self._encodeString(valSer)
            resstr = '%s%s%s' % (keySer, self.separator, valSer)
            results.append(resstr)
        return '\n'.join(results)

    def deserializeValue(self, value):
        results = self.factory()
        if value == '':
            return results
        lines = [line.strip() for line in value.splitlines()]
        for line in lines:
            if not line:
                continue
            key, val = line.split(self.separator, 1)
            key = self._decodeString(key)
            val = self._decodeString(val)
            results[
                self._key_serializer.deserializeValueWithNone(key)] = \
                self._value_serializer.deserializeValueWithNone(val)
        return results
