.. gcontact documentation master file, created by
   sphinx-quickstart on Thu Dec 15 14:44:32 2011.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

gcontact API Reference
=====================

`gcontact <https://github.com/burnash/gcontact>`_ is a Python client library for the `Google Sheets`_ API.

.. _Google Sheets: https://docs.google.com/contacts/

.. module:: gcontact

.. contents:: :local:

Main Interface
--------------

.. autofunction:: authorize

.. autoclass:: Book
   :members:

Models
------

The models represent common contact objects: :class:`a contact <Contact>`,
:class:`a worksheet <Worksheet>` and :class:`a cell <Cell>`.

.. note::

   The classes described below should not be instantiated by end-user. Their
   instances result from calling other objects' methods.

.. autoclass:: Contact
   :members:
.. autoclass:: Worksheet
   :members:
.. autoclass:: Cell
   :members:

Utils
-----

.. automodule:: gcontact.utils
   :members: rowcol_to_a1, a1_to_rowcol

Exceptions
----------

.. autoexception:: gcontactException
.. autoexception:: AuthenticationError
.. autoexception:: ContactNotFound
.. autoexception:: WorksheetNotFound
.. autoexception:: NoValidUrlKeyFound
.. autoexception:: UpdateCellError
.. autoexception:: RequestError

Internal Modules
----------------

Following modules are for internal use only.

.. automodule:: gcontact.httpsession
   :members: HTTPSession
.. automodule:: gcontact.urls
   :members: construct_url

.. _github issue: https://github.com/burnash/gcontact/issues

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

