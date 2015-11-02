###############################################################################
#
# Copyright 2013 by Shoobx, Inc.
#
###############################################################################
"""z3c.insist -- Persistence to ini files"""
import datetime
import decimal
import ConfigParser
from cStringIO import StringIO

import iso8601
import zope.schema
import zope.component
from zope.schema import vocabulary

from z3c.insist import interfaces


NONE_MARKER = '!None'

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
        if config is None:
            config = ConfigParser.RawConfigParser()
            config.optionxform = str
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
        config = ConfigParser.RawConfigParser()
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

    # Flag, indicating that this configuration store can properly support
    # syncing without reloading all objects. To support syncing store has to
    # implement `getConfigHash` method. Change in the hash indicates that child
    # has to be reloaded.
    supports_sync = True

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

    def dump(self, config=None):
        if config is None:
            config = ConfigParser.RawConfigParser()
        for k, v in self.context.items():
            __traceback_info__ = (k, v)
            store = interfaces.IConfigurationStore(v)
            store.section = self.section_prefix + unicode(k).encode('utf-8')
            store.root = self.root
            store.dump(config)
        return config

    def load(self, config):
        if not self.supports_sync:
            # No sync support, just delete all the items
            for k in self.context.keys():
                self.delete(k)

        unloaded = set(self.context.keys())
        for section in self.selectSections(config.sections()):
            loaded = self.loadFromSection(config, section)
            if loaded in unloaded:
                unloaded.remove(loaded)

        # Remove any unloaded items from collection
        for k in unloaded:
            self.delete(k)

    def delete(self, key):
        del self.context[key]

    def _createNewItem(self, config, section):
        if hasattr(self, 'item_factory_typed'):
            obj = self.item_factory_typed(config, section)
        else:
            obj = self.item_factory()
        return obj

    def _createItemConfigStore(self, obj, config, section):
        store = interfaces.IConfigurationStore(obj)
        store.section = section
        store.root = self.root
        return store

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

        # Check if configuration has changed
        if getattr(obj, "__insist_hash__", None) == confhash:
            # Item did not change, skip it
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
        obj.__insist_hash__ = confhash

        if not existing:
            # Let everyone know the object is being added to a collection
            if hasattr(store, 'loadBeforeAdd'):
                obj = store.loadBeforeAdd(name, config)
            self.addItem(name, obj)
            if hasattr(store, 'loadAfterAdd'):
                store.loadAfterAdd(config)

        return name


@zope.interface.implementer(interfaces.IFieldSerializer)
class FieldSerializer(object):
    escape = '!'
    none_marker = NONE_MARKER

    def __init__(self, field, context):
        self.field = field
        self.context = context

    def hasValue(self):
        value = getattr(self.context, self.field.__name__)
        return value is not self.field.missing_value

    def serialize(self):
        value = getattr(self.context, self.field.__name__)
        if value is None:
            return self.none_marker
        else:
            result = self.serializeValue(value)
            return result.replace(self.escape, self.escape * 2)

    def deserialize(self, value):
        if value == self.none_marker:
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
