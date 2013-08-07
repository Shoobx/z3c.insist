###############################################################################
#
# Copyright 2013 by Shoobx, Inc.
#
###############################################################################
"""z3c.insist -- Persistence to ini files"""
import ConfigParser
from cStringIO import StringIO

import zope.schema

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
            config.set(self.section, fn, str(getattr(self.context, fn)))

    def dumps(self):
        config = ConfigParser.SafeConfigParser()
        self.dump(config)
        buf = StringIO()
        config.write(buf)
        return buf.getvalue()

    def load(self, config):
        for fn, field in zope.schema.getFieldsInOrder(self.schema):
            setattr(self.context, fn, config.get(self.section, fn))

    def loads(self, cfgstr):
        buf = StringIO(cfgstr)
        config = ConfigParser.SafeConfigParser()
        config.readfp(buf)
        self.load(config)
