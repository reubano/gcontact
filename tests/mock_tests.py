"""A test suite that doesn't query the Google API.

Avoiding direct network access is beneficial in that it markedly speeds up
testing, avoids error-prone credential setup, and enables validation even if
internet access is unavailable.

"""

from datetime import datetime
import unittest
try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

import mock

import gcontact
from tests import test
from tests import test_utils


class MockUtilsTest(test.UtilsTest):
    pass


class MockgcontactTest(unittest.TestCase):
    """This is the base class for all tests not accessing the API.

    IMPORTANT: This class must be inherited _BEFORE_ a test suite inheriting
    from gcontactTest. This allows MockgcontactTest.setUpClass to clobber the
    one inherited from gcontactTest which authorizes with the Google API.
    """

    @classmethod
    def setUpClass(cls):
        try:
            cls.config = ConfigParser.RawConfigParser()
            cls.gc = gcontact.client.Book(auth={})
        except IOError as e:
            msg = "Can't find %s for reading test configuration. "
            raise Exception(msg % e.filename)


class MockBookTest(MockgcontactTest, test.BookTest):
    """Test for gcontact.Book that mocks out the server response.

    The tests themselves are inherited from BookTest so no redefinition is
    necessary.
    """

    @classmethod
    def setUpClass(cls):
        super(MockBookTest, cls).setUpClass()
        key = '0123456789ABCDEF'
        title = 'This is a contact title'
        url = 'https://docs.google.com/contact/ccc?key=' + key
        updated = datetime.now()
        dev_email = 'foobar@developer.gserviceaccount.com'
        user_name = 'First Last'
        user_email = 'real_email@gmail.com'

        # Initialize mock ConfigParser
        cls.config.add_section('Contact')
        cls.config.set('Contact', 'key', key)
        cls.config.set('Contact', 'title', title)
        cls.config.set('Contact', 'url', url)

        # Set up contact mock
        feed_obj = test_utils.ContactFeed(updated, dev_email)
        feed_obj.add_entry(key, title, user_name, user_email, updated)

        feed = feed_obj.to_xml()
        cls.gc.contacts = mock.Mock(return_value=feed)

        post_mock = mock.MagicMock()
        post_mock.return_value.json.return_value = {'id': key}

        cls.gc.session.post = post_mock


class MockContactTest(MockgcontactTest, test.ContactTest):
    """Test for gcontact.Contact that mocks out the server response.

    The tests themselves are inherited from ContactTest so no redefinition
    is necessary.
    """

    @classmethod
    def setUpClass(cls):
        super(MockContactTest, cls).setUpClass()

        updated = datetime.now()
        user_name = 'First Last'
        user_email = 'real_email@gmail.com'
        key = '0123456789ABCDEF'
        title = 'This is a contact title'
        ws_feed = test_utils.WorksheetFeed(updated, user_name, user_email,
                                           key, title)

        dev_email = 'foobar@developer.gserviceaccount.com'
        ss_feed = test_utils.ContactFeed(updated, dev_email)
        ss_feed.add_entry(key, title, user_name, user_email, updated)

        ws_key = 'AB64KEY'
        ws_title = 'WS Title'
        ws_id = 123456789
        ws_version = 'avkey'
        num_cols = 10
        num_rows = 10
        ws_updated = updated
        ws_feed.add_entry(ws_key, ws_title, ws_id, ws_version, num_cols,
                          num_rows, ws_updated)

        # Initialize mock ConfigParser
        cls.config.add_section('Contact')
        cls.config.set('Contact', 'id', key)
        cls.config.set('Contact', 'title', title)
        cls.config.set('Contact', 'sheet1_title', ws_title)

        # Set up mocks
        cls.gc.contacts = mock.Mock(return_value=ss_feed.to_xml())
        cls.gc.get_worksheets_feed = mock.Mock(return_value=ws_feed.to_xml())
