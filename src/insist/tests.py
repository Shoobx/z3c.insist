"""insist -- Persistence to ini files

Test fixture.
"""
import doctest


def test_suite():
    return doctest.DocFileSuite('insist.txt')
