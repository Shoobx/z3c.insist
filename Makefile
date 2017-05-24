PYTHON = python2.7

all: ve ve/bin/zope-testrunner

ve:
	virtualenv -p $(PYTHON) ve
	ve/bin/pip install -e .[enforce,test]

ve/bin/zope-testrunner:
	ve/bin/pip install zope.testrunner

.PHONY: test
test: ve/bin/zope-testrunner
	ve/bin/zope-testrunner --test-path=${PWD}/src
