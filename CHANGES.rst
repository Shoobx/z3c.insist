Changelog
=========

1.4.0 (unreleased)
------------------

- Dropped support for Python 3.6
- Added support for Python 3.9
- Applied zopefoundation.meta config


1.3.0 (2020-12-15)
------------------

- Dropped support for Python 2 and Python 3.5
- Added support for Python 3.8


1.2.0 (2018-03-31)
------------------

- Use `ConfigParser.read_file()` instead of `ConfigParser.readfp()`, since the
  latter is deprecated.


1.1.4 (2017-05-25)
------------------

- Fixed a senseless bug that was caused by the Py3 port.


1.1.3 (2017-05-25)
------------------

- Fixed a bug in reading the config files.

- Switched to modern ``io.open()`` which supports the ``encoding``
  parameter.

- Make sure that Bytes are properly converted in both directions.


1.1.2 (2017-05-24)
------------------

- Ensure that we always load files in a way that its content is automatically
  converted to unicode.

- Ensure that MANIFEST is complete.

1.1.1 (2017-05-24)
------------------

- Added badges to README.


1.1.0 (2017-05-24)
------------------

- Support for Python 3.5, 3.6 and PyPy.

- Covnerted most doctests to unit tests to ease compatibility effort.

- First public release.


1.0.0 (2017-05-15)
------------------

- Initial release.
