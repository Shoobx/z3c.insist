###############################################################################
#
# Copyright 2013 by Shoobx, Inc.
#
###############################################################################
"""insist -- Persistence to ini files

Test helpers.
"""
import zope.component

from z3c.insist import insist


def setUpSerializers():
    zope.component.provideAdapter(insist.TextFieldSerializer)
    zope.component.provideAdapter(insist.IntFieldSerializer)

