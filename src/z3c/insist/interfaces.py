###############################################################################
#
# Copyright 2013 by Shoobx, Inc.
#
###############################################################################
"""z3c.insist -- Persistence to ini files"""

import zope.interface


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
        """Serialize the context to the configuration file"""

    def load():
        """Load the object state from the configuration file"""


class IFieldSerializer(zope.interface.Interface):
    """Serializer for a particular field type.

    An adapter that takes a field and a value.
    """
    def serialize():
        """Return a string representation of the field"""

    def deserialize(state):
        """Set the field value from a given serialized state"""
