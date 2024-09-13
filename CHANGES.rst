Changelog
=========

1.5.5 (2024-09-13)
------------------

- Fix: Whitelist events instead of blacklisting some, watchdog added EVENT_TYPE_CLOSED_NO_WRITE


1.5.4 (2024-01-15)
------------------

- Change generation of section to folder style


1.5.3 (2023-11-08)
------------------

- Fix inconsistencies in calculating includes paths. Please note that signature of
  SeparateFileConfigurationStoreMixIn.getIncludes has changed.


1.5.2 (2023-05-05)
------------------

- Ignored FileOpenedEvent in dispatch to avoid unnecessary processing of files in IncludingFilesHandler.


1.5.1 (2023-03-23)
------------------

- Added support for Python 3.10 and 3.11

- Ignored FileOpenedEvent in dispatch to avoid unnecessary processing of files.

- Upgraded to the watchdog 3.0.0

1.5.0 (2023-01-24)
------------------

- Relicense under ZPL-2.1.


1.4.2 (2022-04-29)
------------------

- Upgraded to the `watchdog` 2.1.7, which does not support the
  `timeout` parameter in `EventDispatcher.dispatch_events()` any more.


1.4.1 (2021-10-26)
------------------

- Report non-existing included config files. (It helps greatly with debugging.)


1.4.0 (2021-10-18)
------------------

- Implemented ability to include config files for file-based stores.

  + Syntax: ```#include path/to/included.ini```

  + A new `IncludeObserver` component listens to the changes of the included
    files and will update the config of the including file on
    modification. Added and removing new included files is also supported.

- Dropped support for Python 3.6

- Added support for Python 3.9

- Removed last compatibility code with Python 2.

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
