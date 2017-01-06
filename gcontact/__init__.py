# -*- coding: utf-8 -*-

"""
gcontact
~~~~~~~

Google Contacts client library.

"""
from httplib2 import Http, ServerNotFoundError
from collections import defaultdict
from os import path as p, makedirs, getenv
from sys import exit
from json import dumps, loads
from datetime import datetime as dt
from xml.etree.ElementTree import tostring
from xml.etree.ElementTree import Element, SubElement

from oauth2client.service_account import ServiceAccountCredentials
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run_flow
from changanya.simhash import Simhash, SimhashIndex
from meza import process as pr, io

from exceptions import ContactNotFound, UnsupportedFormatError
from httpsession import HTTPSession

__version__ = '0.6.2'
__author__ = 'Reuben Cummings'

DEF_PROPS = {'label': 'home', 'primary': 'true'}
DEF_IM_PROTO = 'GOOGLE_TALK'
SCOPE_FILE = 'gcontact.json'

HOME_DIR = p.expanduser('~')
CREDENTIAL_DIR = p.join(HOME_DIR, '.credentials')
DEF_USER = getenv('USER', getenv('USERNAME', 'default'))
APPLICATION_NAME = 'gContact'
ATOM_NS = 'http://www.w3.org/2005/Atom'
CONTACT_NS = 'http://schemas.google.com/contact/2008'
GOOGLE_NS = 'http://schemas.google.com/g/2005'
BATCH_NS = 'http://schemas.google.com/gdata/batch'
SCOPE = CONTACTS_API_URL = 'https://www.google.com/m8/feeds'
HOME_DOMAINS = {'gmail.com', 'yahoo.com', 'comcast.net'}

# https://developers.google.com/gdata/docs/2.0/elements#schema_37
IM_PROTOCOLS = {
    'aim': 'AIM',
    'gtalk': 'GOOGLE_TALK',
    'googletalk': 'GOOGLE_TALK',
    'google': 'GOOGLE_TALK',
    'icq': 'ICQ',
    'jabber': 'JABBER',
    'msn': 'MSN',
    'qq': 'QQ',
    'skype': 'SKYPE',
    'yahoo': 'YAHOO'}


# https://developers.google.com/gdata/docs/2.0/elements#schema_48
NAME_PROPS = [
    'givenName', 'additionalName', 'familyName', 'namePrefix', 'nameSuffix']

# https://developers.google.com/gdata/docs/2.0/elements#schema_50
ORG_PROPS = [
    'orgName', 'orgTitle', 'orgDepartment', 'orgJobDescription', 'orgSymbol',
    'where']

# https://developers.google.com/google-apps/contacts/v3/reference#Parameters
# DEF_PARAMS = 'alt=json&max-results={max_results}&start-index={page}'
DEF_PARAMS = 'alt={format}&max-results={max_results}'
# DEFAULTS = {'max_results': 8192, 'page': 1, 'user_email': 'default'}
DEFAULTS = {'max_results': 8192, 'user_email': 'default', 'format': 'json'}


def construct_url(**kwargs):
    """Constructs URL to be used for API request.
    """
    urlpattern = 'contacts/{user_email}/full'

    if kwargs.get('batch'):
        urlpattern += '/batch/?%s' % DEF_PARAMS
    elif kwargs.get('contact_id'):
        urlpattern += '/{contact_id}/?%s' % DEF_PARAMS
    else:
        urlpattern += '/?%s' % DEF_PARAMS

    params = pr.merge([DEFAULTS, kwargs])
    return '%s/%s' % (CONTACTS_API_URL, urlpattern.format(**params))


def cont_ns(name):
    return '%s#%s' % (CONTACT_NS, name)


def goog_ns(name):
    return '%s#%s' % (GOOGLE_NS, name)


def listlike(item):
    if hasattr(item, 'keys'):
        listlike = False
    else:
        attrs = {'append', '__next__', 'next', '__reversed__'}
        listlike = attrs.intersection(dir(item))

    return listlike


def get_credentials(keyfile=None, **kwargs):
    if not p.exists(CREDENTIAL_DIR):
        makedirs(CREDENTIAL_DIR)

    credential_path = p.join(CREDENTIAL_DIR, SCOPE_FILE)
    store = Storage(credential_path)
    store._create_file_if_needed()
    credentials = None if kwargs.get('refresh') else store.get()
    invalid = not credentials or credentials.invalid
    has_expired = hasattr(credentials, 'access_token_expired')
    expired = has_expired and credentials.access_token_expired

    if invalid and keyfile:
        if kwargs.get('service_account'):
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                keyfile, SCOPE)

            if kwargs.get('account'):
                credentials = credentials.create_delegated(kwargs['account'])

            credentials.authorize(Http())
        else:
            flow = flow_from_clientsecrets(keyfile, SCOPE)
            flow.user_agent = APPLICATION_NAME
            credentials = run_flow(flow, store)

        store.put(credentials)
    elif expired or not credentials.access_token:
        try:
            credentials.refresh(Http())
        except ServerNotFoundError:
            pass


    return credentials


def _transform_csv_rec(record):
    names = [
        record.get('title', ''),
        record.get('first_name', ''),
        record.get('middle_name', ''),
        record.get('last_name', ''),
        record.get('suffix', '')]

    full_name = ' '.join(n for n in names if n)

    name = {
        'givenName': record.get('first_name', ''),
        'additionalName': record.get('middle_name', ''),
        'familyName': record.get('last_name', ''),
        'namePrefix': record.get('title', ''),
        'nameSuffix': record.get('suffix', '')}

    org = {
        'orgName': record.get('company', ''),
        'orgTitle': record.get('job_title', '')}

    email = {'address': record.get('e_mail', '')}
    _id = [full_name, org['orgName'], org['orgTitle'], email['address']]
    gd_org = {'gd$%s' % k: {'$t': v} for k, v in org.items()}
    gd_org['primary'] = 'true'

    new_rec = {
        'id': ' '.join(_id),
        'title': full_name,
        'gd$name': {'gd$%s' % k: {'$t': v} for k, v in name.items()},
        'gd$organization': [gd_org],
        'gd$email': [{'address': record.get('e_mail', '')}]}

    return new_rec


def parse(value):
    if hasattr(value, 'keys'):
        value = value.get('$t', value)

    return value


def encode(value):
    encoded = hasattr(value, 'keys') and '$t' in value

    if not encoded:
        value = {'$t': value}

    return value


class Contact(object):
    """ A class for a contact object."""
    def __init__(self, account, session, **kwargs):
        self.hashbits = kwargs.get('hashbits', 64)
        self.account = account
        self.session = session
        self._id = kwargs['id']
        self.updated = kwargs['updated']
        self.title = kwargs['title']
        self.note = kwargs.get('content', {})
        self.etag = kwargs.get('gd$etag')
        self.name = kwargs.get('gd$name', {})
        self._organization = kwargs.get('gd$organization', [])
        self._email = kwargs.get('gd$email', [])
        self.im = kwargs.get('gd$im', [])
        self.phone = kwargs.get('gd$phoneNumber', [])
        self.address = kwargs.get('gd$postalAddress', [])
        self.address.extend(kwargs.get('gd$structuredPostalAddress', []))
        def_hash_keys = [('email', 'address'), ('phone', 'uri')]
        self.hash_keys = kwargs.get('hash_keys', def_hash_keys)

        groups = kwargs.get('gContact$groupMembershipInfo', [])
        self.groups = [g['href'] for g in groups if g['deleted'] == 'false']
        self.props = kwargs.get('gd$extendedProperty', [])

    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)

        if name in {'_id', 'updated', 'title', 'note'}:
            value = parse(value)

        return value

    def __setattr__(self, name, value):
        if name in {'_id', 'updated', 'title', 'note'}:
            value = encode(value)

        object.__setattr__(self, name, value)

        if name != 'updated':
            self.updated = dt.utcnow().isoformat()

    def get_primary(self, attr, key=None, default='n/a'):
        items = getattr(self, attr, [{key: default, 'primary': 'true'}])

        for item in items:
            if key and item.get('primary') == 'true':
                value = item.get(key, default)
                break
            elif item.get('primary') == 'true':
                value = item
                break
        else:
            if key and items:
                value = items[0].get(key, default)
            elif items:
                value = items[0]
            else:
                value = default

        return parse(value)

    @property
    def short_id(self):
        return self._id.split('/')[-1]

    @property
    def hash_content(self):
        content = [self.get_primary(*keys) for keys in self.hash_keys]
        return ' '.join([self.title] + content).lower()

    @property
    def simhash(self):
        simhash = Simhash(self.hash_content, hashbits=self.hashbits)
        simhash.cid = self.short_id
        return simhash

    @property
    def organizations(self):
        for organization in self._organization:
            org = parse(organization.get('gd$orgName'))
            title = parse(organization.get('gd$orgTitle'))
            yield ' at '.join(x for x in [title, org] if x)

    @property
    def organization(self):
        org = self.get_primary('_organization', 'gd$orgName')
        title = self.get_primary('_organization', 'gd$orgTitle')
        return ' at '.join(x for x in [title, org] if x)

    @organization.deleter
    def organization(self):
        del self._organization

    @organization.setter
    def organization(self, value, rel='work', **kwargs):
        title, org = value.split(' at ') if ' at ' in value else (None, value)

        new_org = {
          'rel': goog_ns(rel),
          'gd$orgName': encode(org),
          'gd$orgTitle': encode(title)}

        if kwargs.get('label'):
            new_org['label'] = kwargs['label']

        extra = {
            'gd$%s' % prop: kwargs[prop]['$t'] for prop in ORG_PROPS
            if kwargs.get(prop)}

        new_org.update(extra)

        if kwargs.get('primary', True):
            new_org.update({'primary': 'true'})
            prim_org = self.get_primary('_organization', default={})
            prim_org.pop('primary', None)

        _organization = [new_org]

        for organization in self._organization:
            _org = parse(organization.get('gd$orgName'))
            _title = parse(organization.get('gd$orgTitle'))

            if value != ' at '.join(x for x in [_title, _org] if x):
                _organization.append(organization)

        self._organization = _organization

    @property
    def emails(self):
        return (email['address'] for email in self._email)

    @property
    def email(self):
        return self.get_primary('_email', 'address')

    @email.deleter
    def email(self):
        del self._email

    @email.setter
    def email(self, value, rel=None, **kwargs):
        domain = value.split('@')[1].lower()

        if domain.split('.')[0] in self.organization.replace(' ', '').lower():
            rel = 'work'
        elif domain in HOME_DOMAINS:
            rel = 'home'
        else:
            rel = 'other'

        new_email = {'rel': goog_ns(rel), 'address': value}

        if kwargs.get('label'):
            new_email['label'] = kwargs['label']
        elif '.edu' in domain and rel == 'other':
            new_email['label'] = 'School'

        if kwargs.get('primary', True):
            new_email.update({'primary': 'true'})
            prim_email = self.get_primary('_email', default={})
            prim_email.pop('primary', None)

        _email = [new_email]

        for email in self._email:
            if value != email.get('address'):
                _email.append(email)

        self._email = _email

    # def update(self, contact):
    #     self.title = contact.title
    #     self.note = '\n'.join([self.note, contact.note, contact.name])
    #     self.organization.extend(contact.organization)
    #     self.email.extend(contact.email)
    #     self.im.extend(contact.im)
    #     self.phone.extend(contact.phoneNumber)
    #     self.address.extend(contact.address)
    #     self.groups.extend(contact.groups)
    #     self.props.extend(contact.props)
    #     self.clean()

    def clean(self):
        # add entry deduping
        ims = []
        unique_ims = set()

        for email in self.email:
            internet_email = email.get('label', '').lower() == 'internet email'

            if internet_email and not email.get('rel'):
                email['rel'] = cont_ns('home')

        for im in self.im:
            new_protocol = protocol = im.get('protocol', '')

            if not protocol.startswith('http://schemas'):
                stripped = protocol.lower().replace(' ', '').rstrip('chat')
                replaced = stripped.replace('-', '').replace('_', '')

                if stripped in IM_PROTOCOLS:
                    new_protocol = cont_ns(IM_PROTOCOLS[replaced])

            key = (new_protocol, im['address'])

            if key not in unique_ims:
                unique_ims.add(key)
                ims.append(pr.merge(im, {'protocol': new_protocol}))

        self.im = ims

    def _populate_entry(self, entry):
        name = SubElement(entry, 'gd:name')

        SubElement(name, 'gd:fullName').text = self.title

        if self.name:
            for prop in NAME_PROPS:
                if self.name.get('gd$%s' % struct):
                    text = self.name['gd$%s' % struct]['$t']
                    SubElement(name, 'gd:%s' % struct).text = text

        [SubElement(entry, 'gd:email', email) for email in self.email]
        [SubElement(entry, 'gd:im', im) for im in self.im]
        [SubElement(entry, 'gd:extendedProperty', prop) for prop in self.props]

        for org in self.organization:
            details = ft.dfilter(org, ['gd$%s' % prop for prop in ORG_PROPS])
            organization = SubElement(entry, 'gd:organization', details)

            for prop in ORG_PROPS:
                if org.get('gd$%s' % prop):
                    text = org['gd$%s' % prop]['$t']
                    SubElement(organization, 'gd:%s' % prop).text = text

        for phone in self.phone:
            details = ft.dfilter(phone, ['$t'])
            SubElement(entry, 'gd:phoneNumber', details).text = phone['$t']

        structs = {
            'city', 'street', 'region', 'postcode', 'country',
            'formattedAddress'}

        for address in self.address:
            details = ft.dfilter(address, ['$t'])

            if structs.intersection(address):
                addr = SubElement(entry, 'gd:structuredPostalAddress', details)

                for struct in structs:
                    if address.get('gd$%s' % struct):
                        text = address['gd$%s' % struct]['$t']
                        SubElement(addr, 'gd:%s' % struct).text = text
            else:
                text = address['$t']
                SubElement(entry, 'gd:postalAddress', details).text = text

        if self.note:
            SubElement(entry, 'atom:content', {'type': 'text'}).text = self.note

        return entry

    @property
    def newxml(self, *args, **kwargs):
        # https://developers.google.com/google-apps/contacts/v3/#creating_contacts
        entry = Element(
            'atom:entry', {'xmlns:atom': ATOM_NS, 'xmlns:gd': CONTACT_NS})

        SubElement(
            entry,
            'atom:category',
            {'scheme': goog_ns('kind'), 'term': cont_ns('contact')})

        return self._populate_entry(entry)

    @property
    def upxml(self, *args, **kwargs):
        # https://developers.google.com/google-apps/contacts/v3/#updating_contacts
        entry = Element('entry', {'gd:etag': self.etag})
        SubElement(entry, 'id').text = self._id
        SubElement(entry, 'updated').text = self.updated
        SubElement(
            entry,
            'category',
            {'scheme': goog_ns('kind'), 'term': cont_ns('contact')})

        return self._populate_entry(entry)


    def __repr__(self):
        return '<%s id:%s>' % (self.title, self.short_id)

    # def __setattr__(self, name, value):
    #     pass

    # def __delattr__(self, name):
    #     pass

    # def create(self):
    #     headers = {'Content-Type': 'application/atom+xml'}
    #     url = construct_url(user_email=self.account)
    #     r = contact.session.post(url, tostring(self.newxml), headers=headers)
    #     return r.json()

    # def update(self):
    #     headers = {
    #         'Content-Type': 'application/atom+xml', 'If-Match': self.etag}
    #     url = construct_url(user_email=self.account, contact_id=self._id)
    #     r = self.session.put(url, tostring(self.upxml), headers=headers)
    #     return r.json()

    # def delete(self):
    #     url = construct_url(user_email=self.account, contact_id=self._id)
    #     r = self.session.delete(url)
    #     return r.json()

    def __delete__(self):
        return self.delete()

    def __eq__(self, other):
        emails = set(email['address'] for email in self.email)

        if emails.intersection(email['address'] for email in other.email):
            return True

        phones = set(phone['$t'] for phone in self.phone)

        if phones.intersection(phone['$t'] for phone in other.phone):
            return True

        ims = set(im['address'] for im in self.im)

        if ims.intersection(im['address'] for im in other.im):
            return True

        if self.title == other.title:
            pass

        names = set(name['$t'] for name in self.name.values())
        if names.intersection(name['$t'] for name in other.name.values()):
            pass

        return False


class Book(object):
    """An instance of this class communicates with Google Data API.

    :param keyfile: A Service Account Key file path
        https://developers.google.com/api-client-library/python/auth/service-accounts#creatinganaccount

    :param http_session: (optional) A session object capable of making HTTP
        requests while persisting headers. Defaults to
        :class:`~gcontact.httpsession.HTTPSession`.

    >>> book = Book('path/to/keyfile.json')

    """
    def __init__(self, keyfile, **kwargs):
        user = kwargs.get('user', DEF_USER)
        self.hash_keys = kwargs.get('hash_keys')
        self.account = '%s@gmail.com' % user
        self.session = kwargs.get('session', HTTPSession())
        self.format = kwargs.get('format', 'json')
        self.cache_resp = kwargs.get('cache_resp', True)
        self.use_cache = kwargs.get('use_cache', True)
        self.bits = kwargs.get('bits', 3)

        if self.format not in {'json', 'atom', 'rss'}:
            raise UnsupportedFormatError(self.format)

        if self.use_cache:
            args = (self.account, self.session)

            try:
                with open('etag.json') as f:
                    self._etag = loads(f.read())['feed']['gd$etag']
            except (FileNotFoundError, KeyError):
                self._etag = None

            try:
                with open('cache.%s' % self.format) as f:
                    entries = loads(f.read())['feed']['entry']
            except FileNotFoundError:
                self._contacts = None
            except JSONDecodeError:
                self._contacts = []
            else:
                self._contacts = [
                    Contact(
                        *args, hash_keys=self.hash_keys, **e) for e in entries]
        else:
            self._etag = None
            self._contacts = None

        self.credentials = get_credentials(keyfile, **kwargs)
        token = 'Bearer %s' % self.credentials.access_token
        self.session.add_header('Authorization', token)
        self.session.add_header('GData-Version', '3.0')

    @classmethod
    def from_csv(cls, csv_path, **kwargs):
        book = cls(None, use_cache=False)
        records = io.read_csv(csv_path, encoding='ISO-8859-2', sanitize=True)
        kwargs['updated'] = p.getmtime(csv_path)
        mapped = map(_transform_csv_rec, records)
        hashed = pr.hash(mapped, ['id'])
        book._contacts = [
            Contact(None, None, **pr.merge([kwargs, h])) for h in hashed]

        return book

    @property
    def etag(self):
        if self._etag is None:
            args = (self.account, self.session)
            kwargs = {
                'user_email': self.account, 'format': 'json', 'max_results': 0}

            url = construct_url(**kwargs)
            r = self.session.get(url)

            if self.cache_resp:
                with open('etag.json', mode='wb+') as f:
                    f.write(r.content)

            self._etag = r.json()['feed']['gd$etag']

        return self._etag

    @property
    def contacts(self):
        if self._contacts is None:
            args = (self.account, self.session)
            url = construct_url(user_email=self.account, format=self.format)
            r = self.session.get(url)

            if self.cache_resp:
                with open('cache.%s' % self.format, mode='wb+') as f:
                    f.write(r.content)

            if self.format == 'json':
                entries = r.json()['feed']['entry']
                self._contacts = [
                    Contact(
                        *args, hash_keys=self.hash_keys, **e) for e in entries]
            else:
                self._contacts = []

        return self._contacts

    @property
    def hashes(self):
        return [contact.simhash for contact in self.contacts]

    @property
    def contacts_by_name(self):
        contacts = defaultdict(list)

        for contact in self.contacts:
            contacts[contact.title].append(contact)

        return contacts

    @property
    def contacts_by_key(self):
        return {contact.short_id: contact for contact in self.contacts}

    @property
    def hash_index(self):
        return SimhashIndex(self.hashes, bits=self.bits)

    def __getitem__(self, name):
        """Gets a contact.

        :param name: The contact's name.

        :returns: a :class:`~gcontact.Contact` instance.

        If there's more than one contact with same name, returns the first one.

        :raises gcontact.ContactNotFound: if no contact with
                                             specified `name` is found.

        >>> book = Book('path/to/keyfile.json')
        >>> book['Reuben Cummings']
        >>> book[:2]
        >>> book[0]
        """
        try:
            contacts = self.contacts_by_name[name]
        except KeyError as e:
            raise ContactNotFound(e)
        except TypeError:  # it's a slice
            return self.contacts[name]
        else:
            return contacts[0] if contacts else self.contacts[name]

    def __getattr__(self, key):
        """Gets a contact specified by `key`.

        :param key: A key of a contact as it appears in a URL in a browser.

        :returns: a :class:`~gcontact.Contact` instance.

        :raises gcontact.ContactNotFound: if no contact with
                                             specified `key` is found.

        >>> book = Book('path/to/keyfile.json')
        >>> book.0BmgG6nO_6dprdS1MN3d3MkdPa142WFRrdnRRUWl1UFE

        """
        try:
            contact = self.contacts_by_key[key]
        except KeyError as e:
            raise ContactNotFound(e)
        else:
            return contact

    def __delitem__(self, name):
        """Deletes a contact.

        :param key: a contact ID.

        If there's more than one contact with same name, deletes the first one.

        >>> book = Book('path/to/keyfile.json')
        >>> del c['Reuben Cummings']
        """
        return self[name].delete()

    def __delattr__(self, key):
        """Deletes a contact.

        :param key: a contact ID.
        >>> book = Book('path/to/keyfile.json')
        >>> del book.0BmgG6nO_6dprdS1MN3d3MkdPa142WFRrdnRRUWl1UFE
        """
        return getattr(self, key).delete()

    def __iter__(self):
        return iter(self.contacts)

    def dedupe(self, contact=None):
        if contact:
            dupes = self.hash_index.find_dupes(contact.simhash)
            # for simhash in dupes:
            #     print(simhash)
            #     # dupe = getattr(self, simhash.cid)
            #     # contact.update(dupe)
            #     # dupe.delete()
        else:
            pairs = self.hash_index.find_all_dupes()

            for pair in pairs:
                pass
                # contact = getattr(self, pair[0].cid)
                # dupe = getattr(self, pair[1].cid)
                # contact.update(dupe)
                # dupe.delete()

    def create(self, **kwargs):
        """Creates a new contact.

        :param name: A name of a new contact.

        :returns: a :class:`~gcontact.Contact` instance.
        """
        contact = Contact(*args, **kwargs)
        contact.create()
        return contact

    def create_or_update(self, contact):
        dupes = self.hash_index.find_dupes(contact.simhash)
        print('---contact---')
        print(contact.hash_content)
        old_org = contact.organization
        old_email = contact.email
        same = True

        try:
            dupe_hash = next(dupes)
        except StopIteration:
            print('no dupes')
            # self.create(contact)
        else:
            dupe = getattr(self, dupe_hash.cid)
            contact.organization = dupe.organization
            contact.email = dupe.email
            new_org = contact.organization
            new_email = contact.email

            if old_email != new_email:
                print('changed email: %s -> %s' % (old_email, new_email))
                same = False

            if old_org != new_org:
                print('changed org: %s -> %s' % (old_org, new_org))
                same = False

            if same:
                print('no changes!')

def main():
    hash_keys = []
    kwargs = {
        'format': 'json', 'cache_resp': True, 'use_cache': True,
        'hash_keys': hash_keys}
    book = Book(p.join(HOME_DIR, 'client-secret-MCvgr.json'), **kwargs)
    # book.dedupe()
    csv_path = p.join(HOME_DIR, 'linkedin_connections.csv')
    linkedin_book = Book.from_csv(csv_path, hash_keys=hash_keys)

    for contact in linkedin_book[:5]:
        book.create_or_update(contact)

    # book.save()

if __name__ == '__main__':
    main()
