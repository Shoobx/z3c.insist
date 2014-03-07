###############################################################################
#
# Copyright 2013 by Shoobx, Inc.
#
###############################################################################
"""z3c.insist -- Persistence to ini files"""
import ConfigParser
from cStringIO import StringIO

import zope.schema
import zope.component
from zope.schema import vocabulary

from z3c.insist import interfaces


@zope.interface.implementer(interfaces.IConfigurationStore)
class ConfigurationStore(object):

    _section = None
    fields = None
    ignore_fields = None
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
            if not config.has_option(self.section, fn):
                continue
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
    """

    def addItem(self, name, obj):
        self.context[name] = obj

    def dump(self, config=None):
        if config is None:
            config = ConfigParser.RawConfigParser()
        for k, v in self.context.items():
            __traceback_info__ = (k, v)
            store = interfaces.IConfigurationStore(v)
            store.section = self.section_prefix + k
            store.root = self.root
            store.dump(config)
        return config

    def load(self, config):
        for k in list(self.context):
            del self.context[k]

        for section in config.sections():
            if not section.startswith(self.section_prefix):
                continue
            obj = self.item_factory()
            store = interfaces.IConfigurationStore(obj)
            store.section = section
            store.root = self.root
            store.load(config)
            name = section[len(self.section_prefix):]
            if hasattr(store, 'loadBeforeAdd'):
                obj = store.loadBeforeAdd(name, config)
            self.addItem(name, obj)
            if hasattr(store, 'loadAfterAdd'):
                store.loadAfterAdd(config)


@zope.interface.implementer(interfaces.IFieldSerializer)
class FieldSerializer(object):
    escape = '!'
    none_marker = '!None'

    def __init__(self, field, context):
        self.field = field
        self.context = context

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
    zope.schema.interfaces.IBool, zope.interface.Interface)
class BoolFieldSerializer(FieldSerializer):
    def serializeValue(self, value):
        return str(value)

    def deserializeValue(self, value):
        return value == 'True'


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
        except LookupError, err:
            # The term does not exist any more. Since in most cases the for
            # user-defined vocabularies the value == token, we'll just return
            # the str'ed value.
            return str(value)

    def deserializeValue(self, value):
        vocabulary = self._getVocabulary()
        try:
            return vocabulary.getTermByToken(value).value
        except LookupError, err:
            # The term does not exist any more. Since in most cases the for
            # user-defined vocabularies the value == token, we'll just return
            # the str'ed value.
            return unicode(value)


class SequenceFieldSerializer(FieldSerializer):

    sequence = None
    separator = ", "

    def serializeValue(self, value):
        item_serializer =  zope.component.getMultiAdapter(
            (self.field.value_type, self.context), interfaces.IFieldSerializer)
        results = []
        for item in value:
            results.append(item_serializer.serializeValue(item))
        return self.separator.join(results)

    def deserializeValue(self, value):
        item_serializer =  zope.component.getMultiAdapter(
            (self.field.value_type, self.context), interfaces.IFieldSerializer)
        results = []
        if value == '':
            return self.sequence()
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
