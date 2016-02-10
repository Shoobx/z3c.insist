###############################################################################
#
# Copyright 2013 by Shoobx, Inc.
#
###############################################################################
"""z3c.insist -- Persistence to ini files"""

import zope.interface
import zope.schema
from zope.lifecycleevent import ObjectModifiedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

NONE_MARKER = '!None'


class IConfigurationStore(zope.interface.Interface):

    schema = zope.schema.Field(
        title=u"Schema",
        description=u"The schema to serialize",
        )
    section = zope.schema.TextLine(
        title=u"Section",
        description=u"Configuration file section to export this object in",
        )

    def dump():
        """Serialize the context to the configuration file.

        Returns a ConfigParser object.
        """

    def load(config):
        """Load the object state from the configuration file."""

    def dumps():
        """Serialize the context to the configuration file.

        Returns a string.
        """

    def loads(config):
        """Load the object state from the configuration as a string."""


class ISeparateFileConfigurationStore(IConfigurationStore):
    """Collection Configuration Store Utilizing a Separate File

    This is a configuration store for collections that stores all
    configuration for the collection intoa  separate file.
    """

    def getConfigPath():
        """Get configuration directory path.

        Returns the path of the drirectory in which to store the configuration.
        """
        raise NotImplemented

    def getConfigFilename():
        """Return the config filename."""


class IFieldSerializer(zope.interface.Interface):
    """Serializer for a particular field type.

    An adapter that takes a field and a value.
    """
    def hasValue():
        """Return True if the value is not empty/missing."""

    def serialize(ignoreDefault=False):
        """Return a string representation of the field.

        If ignoreDefault is True, and the value is the default, return None,
        which signals insist to ignore the value for dumping purposes.
        """

    def deserialize(state):
        """Set the field value from a given serialized state"""

    def serializeValueWithNone(value):
        """Return NONE_MARKER if value is None, otherwise serialize normally.
        """

    def serializeValue(value):
        """Convert the real native type -> string.

        Always must return a properly serialized string.
        """

    def deserializeValueWithNone(value):
        """Return None if value is NONE_MARKER, otherwise deserialie normally.
        """

    def deserializeValue(value):
        """Convert real string -> native type.

        Must always return a valid value for the given field.
        """


class IObjectConfigurationLoadedEvent(IObjectModifiedEvent):
    """Object configuration loaded event interface"""


@zope.interface.implementer(IObjectConfigurationLoadedEvent)
class ObjectConfigurationLoadedEvent(ObjectModifiedEvent):
    """Object configuration loaded"""


class ConfigurationLoadError(Exception):
    """Configuration load error"""
