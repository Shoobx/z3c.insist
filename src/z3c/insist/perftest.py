###############################################################################
#
# Copyright 2015 by Shoobx, Inc.
#
###############################################################################
"""Insist Performance Tests"""
import ConfigParser
import argparse
import collections
import datetime
import os
import prettytable
import shutil
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
        self.repeatedText = TO_BE_REPEATED * (number % 10)
        self.isEven = bool(number % 2)
        self.date = datetime.date.today() + datetime.timedelta(days=number)

    def __repr__(self):
        return 'NumberObject(%s)' % self.name

class SimpleCollectionStore(insist.CollectionConfigurationStore):
    schema = INumberObject
    section_prefix = 'number:'
    item_factory = NumberObject

@zope.component.adapter(INumberObject)
@zope.interface.implementer(interfaces.IConfigurationStore)
class SimpleItemStore(insist.ConfigurationStore):
    schema = INumberObject

def simpleUpdateConfigFile():
    # There is only one choice to update the monolithic file. Load the file,
    # update the section and resave.
    cp = ConfigParser.RawConfigParser()
    cp.optionxform = str
    with open(os.path.join(DATA_DIRECTORY, 'main.ini'), 'r') as file:
        cp.readfp(file)
    cp.set('number:0', 'repeatedText', 'Modified')
    with open(os.path.join(DATA_DIRECTORY, 'main.ini'), 'w') as file:
        cp.write(file)


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

def fileUpdateConfigFile():
    # We only need to update the right file.
    cp = ConfigParser.RawConfigParser()
    cp.optionxform = str
    with open(os.path.join(DATA_DIRECTORY, 'number:0.ini'), 'r') as file:
        cp.readfp(file)
    cp.set('number:0', 'repeatedText', 'Modified')
    with open(os.path.join(DATA_DIRECTORY, 'number:0.ini'), 'w') as file:
        cp.write(file)


class PerformanceTest(object):
    storeFactories = (
        (SimpleCollectionStore, SimpleItemStore, simpleUpdateConfigFile),
        (FileItemsCollectionStore, FileItemStore, fileUpdateConfigFile),
        )

    def __init__(self, amount=1000):
        self.results = collections.OrderedDict()
        self.amount = amount

    def generateData(self):
        coll = collections.OrderedDict()
        for number in range(self.amount):
            coll[unicode(number)] = NumberObject(number)
        return coll

    def runOne(self, collectionFactory, itemFactory, updateCallable, data):
        zope.component.testing.setUp(None)
        testing.setUpSerializers()
        shutil.rmtree(DATA_DIRECTORY)
        os.mkdir(DATA_DIRECTORY)

        # Register the item factory as an adapter
        zope.component.provideAdapter(itemFactory)

        # Create collection store.
        store = collectionFactory(data)
        main_ini = os.path.join(DATA_DIRECTORY, 'main.ini')

        # 1. Dump data.
        print collectionFactory.__name__, 'Dump...'
        dump_start = time.time()
        config = store.dump()
        with open(main_ini, 'w') as file:
            config.write(file)
        dump_end = time.time()

        # 2. Load data.
        print collectionFactory.__name__, 'Load...'
        data2 = collections.OrderedDict()
        store2 = collectionFactory(data2)
        load_start = time.time()
        config = store2._createConfigParser()
        with open(main_ini, 'r') as file:
            config.readfp(file)
        store2.load(config)
        load_end = time.time()

        # 3. Update data.
        print collectionFactory.__name__, 'Update...'
        # Modify the original data.
        updateCallable()
        # Now update previously loaded data.
        update_start = time.time()
        store2 = collectionFactory(data2)
        config = store2._createConfigParser()
        with open(main_ini, 'r') as file:
            config.readfp(file)
        store2.load(config)
        update_end = time.time()
        assert data2['0'].repeatedText == u'Modified'

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
        for coll, item, update in self.storeFactories:
            self.runOne(coll, item, update, data)

parser = argparse.ArgumentParser(
    prog='perftest',
    description='Test performance of z3c.insist.')
parser.add_argument(
    '-a', '--amount', dest='amount', type=int, default=10000,
    help="The amount of sections to create.")
parser.add_argument(
    '-v', '--verbose', dest='verbose', action="count", default=0,
    help="Increase verbosity of the output.")
parser.add_argument(
    '-q', '--quiet', dest='verbose', action='store_const', const=0,
    help="Print nothing")


def main(args=sys.argv[1:]):
    args = parser.parse_args(args)
    pt = PerformanceTest(args.amount)
    pt.run()
    pt.printResults()
