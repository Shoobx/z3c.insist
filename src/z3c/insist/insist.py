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

    def dump(self):
        config = ConfigParser.SafeConfigParser()
        config.add_section(self.section)
        for fn, field in zope.schema.getFieldsInOrder(self.schema):
            serializer = zope.component.getMultiAdapter(
                (field, self.context), interfaces.IFieldSerializer)
            state = serializer.serialize()
            config.set(self.section, fn, state)
        return config

    def dumps(self):
        config = self.dump()
        buf = StringIO()
        config.write(buf)
        return buf.getvalue()

    def load(self, config):
        for fn, field in zope.schema.getFieldsInOrder(self.schema):
            serializer = zope.component.getMultiAdapter(
                (field, self.context), interfaces.IFieldSerializer)
            serializer.deserialize(config.get(self.section, fn))

    def loads(self, cfgstr):
        buf = StringIO(cfgstr)
        config = ConfigParser.SafeConfigParser()
        config.readfp(buf)
        self.load(config)


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
