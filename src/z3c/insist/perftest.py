###############################################################################
#
# Copyright 2015 by Shoobx, Inc.
#
###############################################################################
"""Insist Performance Tests"""
import prettytable
import collections
import datetime
import os
import sys
import time
import zope.component
import zope.component.testing
import zope.interface
import zope.schema

from z3c.insist import interfaces, insist, testing

TO_BE_REPEATED = u'Some nice text.\n'

DATA_DIRECTORY = os.path.join(os.curdir, 'perf-data')

class INumberObject(zope.interface.Interface):

    name = zope.schema.TextLine()
    number = zope.schema.Int()
    repeatedText = zope.schema.TextLine()
    isEven = zope.schema.Bool()
    date = zope.schema.Date()

@zope.interface.implementer(INumberObject)
class NumberObject(object):
    name = None
    number =None
    repeatedText = None
    isEven = None
    data = None

    def __init__(self, number=None):
        if number is None:
            return
        self.name = unicode(number)
        self.number = number
        self.repeatedText = TO_BE_REPEATED * number
        self.isEven = bool(number % 2)
        self.date = datetime.date.today() + datetime.timedelta(days=number)


class SimpleCollectionStore(insist.CollectionConfigurationStore):
    schema = INumberObject
    section_prefix = 'number:'
    item_factory = NumberObject

@zope.component.adapter(INumberObject)
@zope.interface.implementer(interfaces.IConfigurationStore)
class SimpleItemStore(insist.ConfigurationStore):
    schema = INumberObject


class FileItemsCollectionStore(insist.FileSectionsCollectionConfigurationStore):
    schema = INumberObject
    section_prefix = 'number:'
    item_factory = NumberObject

    def getConfigPath(self):
        return DATA_DIRECTORY

@zope.component.adapter(INumberObject)
@zope.interface.implementer_only(interfaces.IConfigurationStore)
class FileItemStore(insist.SeparateFileConfigurationStore):
    dumpSectionStub = False
    schema = INumberObject

    def getConfigPath(self):
        return DATA_DIRECTORY



class PerformanceTest(object):
    storeFactories = (
        #(SimpleCollectionStore, SimpleItemStore),
        (FileItemsCollectionStore, FileItemStore),
        )

    def __init__(self):
        self.results = collections.OrderedDict()

    def generateData(self, amount=1000):
        coll = collections.OrderedDict()
        for number in range(amount):
            coll[unicode(number)] = NumberObject(number)
        return coll

    def runOne(self, collectionFactory, itemFactory, data):
        zope.component.testing.setUp(None)
        testing.setUpSerializers()

        # Register the item factory as an adapter
        zope.component.provideAdapter(itemFactory)

        # Create collection store.
        store = collectionFactory(data)
        main_ini = os.path.join(DATA_DIRECTORY, 'main.ini')

        # 1. Dump data.
        dump_start = time.time()
        config = store.dump()
        with open(main_ini, 'w') as file:
            config.write(file)
        dump_end = time.time()

        # 2. Load data.
        data2 = collections.OrderedDict()
        store2 = collectionFactory(data2)
        load_start = time.time()
        config = store2._createConfigParser()
        with open(main_ini, 'r') as file:
            config.readfp(file)
        store2.load(config)
        load_end = time.time()

        # 3. Update data.
        # Modify the original data and redump.
        data['0'].repeatedText = u'Modified'
        config = store.dump()
        with open(main_ini, 'w') as file:
            config.write(file)
        # Now update previously loaded data.
        update_start = time.time()
        config = store2._createConfigParser()
        with open(main_ini, 'r') as file:
            config.readfp(file)
        store2.load(config)
        update_end = time.time()

        zope.component.testing.tearDown(None)

        self.results[collectionFactory.__name__] = [
            dump_end - dump_start,
            load_end - load_start,
            update_end - update_start,
            ]

    def printResults(self):
        pt = prettytable.PrettyTable(
            ['Store Name', 'Dump', 'Load', 'Update'])
        for name, res in self.results.items():
            fmt_res = ['%0.3fs' % e for e in res]
            pt.add_row([name] + fmt_res)
        print pt

    def run(self):
        data = self.generateData()
        for collectionFactory, itemFactory in self.storeFactories:
            self.runOne(collectionFactory, itemFactory, data)

def main(args=None):
    if not os.path.exists(DATA_DIRECTORY):
        os.mkdir(DATA_DIRECTORY)
    pt = PerformanceTest()
    pt.run()
    pt.printResults()
