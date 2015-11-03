###############################################################################
#
# Copyright 2013-15 by Shoobx, Inc.
#
###############################################################################
"""z3c.insist -- Persistence to ini files"""
import ConfigParser
import datetime
import decimal
import os
import time
from cStringIO import StringIO

import iso8601
import zope.schema
import zope.component
from zope.schema import vocabulary

from z3c.insist import interfaces

class FilesystemMixin(object):
    """Hooks to abstract file access."""

    def fileExists(self, path):
        return os.path.exists(path)

    def getFileModTime(self, path):
        if not self.fileExists(path):
            return None
        return os.path.getmtime(path)

    def openFile(self, path, mode='r'):
        return open(path, mode)


@zope.interface.implementer(interfaces.IConfigurationStore)
class ConfigurationStore(object):

    _section = None
    fields = None
    ignore_fields = None
    ignore_missing = False
    root = None

    def __init__(self, context):
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

    @classmethod
    def makeStore(cls, value, schema, section=None):
        store = cls(value)
        store.schema = schema
        if section is not None:
            store.section = section
        return store

    def _createConfigParser(self, config=None):
        if config is None:
            config = ConfigParser.RawConfigParser()
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
            __traceback_info__ = (self.section, self.schema, fn)
            if hasattr(self, 'dump_%s' % fn):
                serializer = CustomSerializer(field, self.context, self)
            else:
                serializer = zope.component.getMultiAdapter(
                    (field, self.context), interfaces.IFieldSerializer)
            if self.ignore_missing and not serializer.hasValue():
                continue
            state = serializer.serialize()
            config.set(self.section, fn, state)

    def dump(self, config=None):
        config = self._createConfigParser(config)
        self._dump(config)
        return config

    def dumps(self):
        config = self.dump()
        buf = StringIO()
        config.write(buf)
        return buf.getvalue()

    def load(self, config):
        for fn, field in self._get_fields():
            if self.fields is not None and fn not in self.fields:
                continue
            # XXX: __name__ is a special for RawConfigParser
            #      http://bugs.python.org/msg215809
            if not config.has_section(self.section):
                continue
            elif fn not in config.options(self.section):
                continue
            #if not config.has_option(self.section, fn):
            #    continue
            __traceback_info__ = (self.section, self.schema, fn)
            if hasattr(self, 'load_%s' % fn):
                serializer = CustomSerializer(field, self.context, self)
            else:
                serializer = zope.component.getMultiAdapter(
                    (field, self.context), interfaces.IFieldSerializer)
            serializer.deserialize(config.get(self.section, fn))
        zope.event.notify(
            interfaces.ObjectConfigurationLoadedEvent(
                self.context))

    def loads(self, cfgstr):
        buf = StringIO(cfgstr)
        config = self._createConfigParser()
        config.readfp(buf)
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
        self.context[name] = obj

    def deleteItem(self, name):
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
                v, config, self.section_prefix + unicode(k).encode('utf-8'))
            store.dump(config)
        return config

    def load(self, config):
        unloaded = set(self.context.keys())
        for section in self.selectSections(config.sections()):
            loaded = self.loadFromSection(config, section)
            if loaded in unloaded:
                unloaded.remove(loaded)

        # Remove any unloaded items from collection
        for k in unloaded:
            del self.context[k]

    def getSectionHash(self, obj, config, section):
        return hash(tuple(config.items(section)))

    def _createNewItem(self, config, section):
        if hasattr(self, 'item_factory_typed'):
            obj = self.item_factory_typed(config, section)
        else:
            obj = self.item_factory()
        return obj

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

        confhash = self.getSectionHash(obj, config, section)

        # Check if configuration has changed. Note that in some cases when the
        # object is new, the hash might not have been computable and thus
        # None. In those cases we want to go on.
        if confhash is not None and \
          getattr(obj, "__insist_hash__", None) == confhash:
            return name

        # Config has changed, we can load object with properties from
        # configuration.

        # First of all, make sure class of the item didn't change. Otherwise we
        # have to remove it and re-add, because property set for it may be
        # completely different.
        if existing:
            newobj = self._createNewItem(config, section)
            if newobj.__class__ is not obj.__class__:
                # Yeah, class have changed, let's replace the item
                del self.context[name]
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
            subconfig.write(file)

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
    pass

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
        raise NotImplemented

    def getSectionPath(self, section):
        return os.path.join(self.getConfigPath(), section + self.filePostfix)

    def selectSections(self, sections):
        baseDir = self.getConfigPath()
        file_sections = [
            filename[:-len(self.filePostfix)]
            for filename in os.listdir(baseDir)
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

    def getSectionHash(self, obj, config, section):
        # 1. Generate the config file path.
        sectionPath = self.getSectionPath(section)
        # 2. Use the mod time of the file as a hash
        return self.getFileModTime(sectionPath)


@zope.interface.implementer(interfaces.IFieldSerializer)
class FieldSerializer(object):
    escape = '!'

    def __init__(self, field, context):
        self.field = field
        self.context = context

    def hasValue(self):
        value = getattr(self.context, self.field.__name__)
        return value is not self.field.missing_value

    def serialize(self):
        value = getattr(self.context, self.field.__name__)
        if value is None:
            return interfaces.NONE_MARKER
        else:
            result = self.serializeValue(value)
            return result.replace(self.escape, self.escape * 2)

    def deserialize(self, value):
        if value == interfaces.NONE_MARKER:
            decoded = None
        else:
            value = value.replace(self.escape * 2, self.escape)
            decoded = self.deserializeValue(value)
        setattr(self.context, self.field.__name__, decoded)


@zope.component.adapter(
    zope.schema.interfaces.IBytes, zope.interface.Interface)
class BytesFieldSerializer(FieldSerializer):
    def serializeValue(self, value):
        return value

    def deserializeValue(self, value):
        return value


@zope.component.adapter(
    zope.schema.interfaces.IText, zope.interface.Interface)
class TextFieldSerializer(FieldSerializer):
    def serializeValue(self, value):
        return value.encode('utf-8')

    def deserializeValue(self, value):
        return unicode(value, 'utf-8')


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
        return value == 'True'


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

    def serializeValue(self, value):
        item_serializer = zope.component.getMultiAdapter(
            (self.field.value_type, self.context), interfaces.IFieldSerializer)
        results = []
        for item in value:
            results.append(item_serializer.serializeValue(item))
        return self.separator.join(results)

    def deserializeValue(self, value):
        if value == '':
            return self.sequence()
        item_serializer = zope.component.getMultiAdapter(
            (self.field.value_type, self.context), interfaces.IFieldSerializer)
        results = []
        for item in value.split(self.separator):
            __traceback_info__ = item, self.field.value_type
            item = item.strip()
            results.append(item_serializer.deserializeValue(item))
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
