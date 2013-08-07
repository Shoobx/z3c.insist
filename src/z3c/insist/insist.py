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

    section = 'default'

    def __init__(self, context):
        self.context = context

    @classmethod
    def makeStore(cls, value, schema, section=None):
        store = cls(value)
        store.schema = schema
        if section is not None:
            store.section = section
        return store

    def dump(self, config):
        config.add_section(self.section)
        for fn, field in zope.schema.getFieldsInOrder(self.schema):
            serializer = zope.component.getMultiAdapter(
                (field, self.context), interfaces.IFieldSerializer)
            state = serializer.serialize()
            config.set(self.section, fn, state)

    def dumps(self):
        config = ConfigParser.SafeConfigParser()
        self.dump(config)
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


@zope.component.adapter(
    zope.schema.interfaces.ITextLine, zope.interface.Interface)
@zope.interface.implementer(interfaces.IFieldSerializer)
class TextFieldSerializer(object):
    def __init__(self, field, context):
        self.field = field
        self.context = context

    def serialize(self):
        value = getattr(self.context, self.field.__name__)
        return value.encode('utf-8')

    def deserialize(self, value):
        decoded = unicode(value, 'utf-8')
        setattr(self.context, self.field.__name__, decoded)

