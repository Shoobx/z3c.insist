"""insist -- Persistence to ini files"""
import ConfigParser
from cStringIO import StringIO

import zope.schema


class ConfigurationStore(object):

    section = 'default'

    def __init__(self, schema, section=None):
        self.schema = schema
        if section is not None:
            self.section = section

    def dump(self, value, config):
        config.add_section(self.section)
        for fn, field in zope.schema.getFieldsInOrder(self.schema):
            config.set(self.section, fn, str(getattr(value, fn)))

    def dumps(self, value):
        config = ConfigParser.SafeConfigParser()
        self.dump(value, config)
        buf = StringIO()
        config.write(buf)
        return buf.getvalue()

    def load(self, value, config):
        for fn, field in zope.schema.getFieldsInOrder(self.schema):
            setattr(value, fn, config.get(self.section, fn))

    def loads(self, value, cfgstr):
        buf = StringIO(cfgstr)
        config = ConfigParser.SafeConfigParser()
        config.readfp(buf)
        self.load(value, config)
