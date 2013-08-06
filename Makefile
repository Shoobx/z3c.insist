PYTHON = python2.7


all: bin/test

bootstrap.py:
	wget http://downloads.buildout.org/2/bootstrap.py

ve:
	virtualenv -p $(PYTHON) ve

bin/buildout: ve bootstrap.py
	ve/bin/pip install --upgrade setuptools
	ve/bin/python bootstrap.py

bin/test: bin/buildout buildout.cfg setup.py versions.cfg
	bin/buildout
	touch bin/test

test: bin/test
	bin/test
