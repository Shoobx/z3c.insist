###############################################################################
#
# Copyright 2015 by Shoobx, Inc.
#
###############################################################################
"""Enforcer Sample Tests"""
import argparse
import collections
import logging
import os
import sys
import time
import zope.component
from z3c.insist import insist, enforce, interfaces, perftest, testing


class FileItemsCollectionStoreEventHandler(
        enforce.FileSectionsCollectionConfigurationStoreEventHandler):
    storeFactory = perftest.FileItemsCollectionStore

    def createStore(self, section):
        store = self.storeFactory(self.context)
        store.root = self.context
        return store

class EnforcerTest(object):

    def __init__(self, amount=1000):
        self.amount = amount

    def setUp(self):
        zope.component.testing.setUp(None)
        testing.setUpSerializers()
        zope.component.provideAdapter(perftest.FileItemStore)
        zope.component.provideSubscriptionAdapter(
            FileItemsCollectionStoreEventHandler)

    def generateData(self):
        self.data = collections.OrderedDict()
        for number in range(self.amount):
            self.data[unicode(number)] = perftest.NumberObject(number)

    def dumpData(self):
        print 'Dumping data into ...', perftest.DATA_DIRECTORY
        store = perftest.FileItemsCollectionStore(self.data)
        main_ini = os.path.join(perftest.DATA_DIRECTORY, 'main.ini')
        config = store.dump()
        with open(main_ini, 'w') as file:
            config.write(file)
        return store

    def printItem(self, number):
        obj = self.data.get(number)
        if obj is None:
            print 'No item found.'
            return
        print obj.name
        print '-' * len(obj.name)
        print 'Number:', obj.number
        print 'Is Even:', obj.isEven
        print 'Date:', obj.date
        print 'Repeated Text:', obj.repeatedText

    def run(self):
        self.setUp()
        self.generateData()
        store = self.dumpData()

        enforcer = enforce.EventHandlerSubscriberEnforcer(
            perftest.DATA_DIRECTORY, self.data)
        enforcer.start()

        try:
            while True:
                number = raw_input('Number: ')
                if number is 'q':
                    enforcer.stop()
                    break
                self.printItem(number)
        except KeyboardInterrupt:
            enforcer.stop()


parser = argparse.ArgumentParser(
    prog='perftest',
    description='Test performance of z3c.insist.')
parser.add_argument(
    '-a', '--amount', dest='amount', type=int, default=10000,
    help="The amount of sections to create.")
parser.add_argument(
    '-v', '--verbose', dest='loglevel', action="count", default=0,
    help="Increase verbosity of the output.")
parser.add_argument(
    '-q', '--quiet', dest='loglevel', action='store_const', const=0,
    help="Print nothing")


def main(args=sys.argv[1:]):
    args = parser.parse_args(args)
    logging.basicConfig(level=max(10, 40-(10*args.loglevel)))
    pt = EnforcerTest(args.amount)
    pt.run()
