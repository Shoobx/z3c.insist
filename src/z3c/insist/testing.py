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
    zope.component.provideAdapter(insist.TextLineFieldSerializer)
    zope.component.provideAdapter(insist.IntFieldSerializer)
    zope.component.provideAdapter(insist.DecimalFieldSerializer)
    zope.component.provideAdapter(insist.ChoiceFieldSerializer)
    zope.component.provideAdapter(insist.ListFieldSerializer)
    zope.component.provideAdapter(insist.TupleFieldSerializer)
    zope.component.provideAdapter(insist.BoolFieldSerializer)
    zope.component.provideAdapter(insist.DateFieldSerializer)
    zope.component.provideAdapter(insist.DateTimeFieldSerializer)
    zope.component.provideAdapter(insist.DictFieldSerializer)
