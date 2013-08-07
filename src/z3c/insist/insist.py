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

from z3c.insist import interfaces


@zope.interface.implementer(interfaces.IConfigurationStore)
class ConfigurationStore(object):

    section = 'object'

    def __init__(self, context):
        self.context = context

    @classmethod
    def makeStore(cls, value, schema, section=None):
        store = cls(value)
        store.schema = schema
        if section is not None:
            store.section = section
        return store

    def dump(self, config=None):
        if config is None:
            config = ConfigParser.SafeConfigParser()
        config.add_section(self.section)
        for fn, field in zope.schema.getFieldsInOrder(self.schema):
            __traceback_info__ = (self.section, self.schema, fn)
            serializer = zope.component.getMultiAdapter(
                (field, self.context), interfaces.IFieldSerializer)
            state = serializer.serialize(self)
            config.set(self.section, fn, state)
        return config

    def dumps(self):
        config = self.dump()
        buf = StringIO()
        config.write(buf)
        return buf.getvalue()

    def load(self, config):
        for fn, field in zope.schema.getFieldsInOrder(self.schema):
            __traceback_info__ = (self.section, self.schema, fn)
            serializer = zope.component.getMultiAdapter(
                (field, self.context), interfaces.IFieldSerializer)
            serializer.deserialize(config.get(self.section, fn), self)

    def loads(self, cfgstr):
        buf = StringIO(cfgstr)
        config = ConfigParser.SafeConfigParser()
        config.readfp(buf)
        self.load(config)


class CollectionConfigurationStore(ConfigurationStore):
    """A configuration store for collections.

    Subclasses must provide the following attributes:

       * schema
       * section_prefix
       * item_factory
    """

    def dump(self):
        config = super(CollectionConfigurationStore, self).dump()
        for k, v in self.context.items():
            store = interfaces.IConfigurationStore(v)
            store.section = self.section_prefix + k
            store.dump(config)
        return config

    def load(self, config):
        super(CollectionConfigurationStore, self).load(config)

        for k in list(self.context):
            del self.context[k]

        for section in config.sections:
            if not section.startswith(self.section_prefix):
                continue
            store = interfaces.IConfigurationStore(self.item_factory())
            store.section = section
            store.load(config)
        return config


@zope.interface.implementer(interfaces.IFieldSerializer)
class FieldSerializer(object):
    escape = '!'
    none_marker = '!None'

    def __init__(self, field, context):
        self.field = field
        self.context = context

    def serialize(self, store):
        value = getattr(self.context, self.field.__name__)
        if value is None:
            return self.none_marker
        elif hasattr(store, 'dump_' + self.field.__name__):
            # Legacy hook
            return getattr(store, 'dump_' + self.field.__name__)(value)
        else:
            result = self.serializeValue(value)
            return result.replace(self.escape, self.escape * 2)

    def deserialize(self, value, store):
        if value == self.none_marker:
            decoded = None
        elif hasattr(store, 'load_' + self.field.__name__):
            # Legacy hook
            decoded = getattr(store, 'load_' + self.field.__name__)(value)
        else:
            value = value.replace(self.escape * 2, self.escape)
            decoded = self.deserializeValue(value)
        setattr(self.context, self.field.__name__, decoded)


@zope.component.adapter(
    zope.schema.interfaces.ITextLine, zope.interface.Interface)
class TextFieldSerializer(FieldSerializer):
    def serializeValue(self, value):
        return value.encode('utf-8')

    def deserializeValue(self, value):
        return unicode(value, 'utf-8')


@zope.component.adapter(
    zope.schema.interfaces.IInt, zope.interface.Interface)
class IntFieldSerializer(FieldSerializer):
    def serializeValue(self, value):
        return str(value)

    def deserializeValue(self, value):
        return int(value)
