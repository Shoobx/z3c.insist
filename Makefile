PYTHON ?= python3.9

all: ve ve/bin/zope-testrunner

ve:
	$(PYTHON) -m venv ve; \
	  ve/bin/pip install --upgrade setuptools; \
	  ve/bin/pip install --upgrade wheel
	ve/bin/pip install -e .[enforce,test]

ve/bin/zope-testrunner:
	ve/bin/pip install zope.testrunner

.PHONY: test
test: ve/bin/zope-testrunner
	ve/bin/zope-testrunner --test-path=${PWD}/src
