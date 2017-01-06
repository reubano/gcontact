# -*- coding: utf-8 -*-

"""
gcontact.exceptions
~~~~~~~~~~~~~~~~~~

Exceptions used in gcontact.

"""


class gcontactException(Exception):
    """A base class for gcontact's exceptions."""


class AuthenticationError(gcontactException):
    """An error during authentication process."""


class ContactNotFound(gcontactException):
    """Trying to open non-existent or inaccessible contact."""


class ImportException(gcontactException):
    """An error during import."""


class UnsupportedFormatError(gcontactException):
    pass


class RequestError(gcontactException):
    """Error while sending API request."""
