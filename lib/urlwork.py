import cgi
import logging
import re
import sys
import urllib
import urlparse

import requests
import urlnorm


# We will strip any params that match these patterns
EXCLUDE_PARAM_PATTERNS = [
    r'^utm_',
    r'^ex_cid$', # seen on grantland.com URLs
]


def canonicalize(url):
    """Canonicalize a URL in just a few easy steps:

        1. Resolve any redirects
        2. Normalize the URL
        3. Strip any superflous query params
        4. Sort any remaining query params
        5. Profit!

    This relies on the urlnorm module for normalization, and, at the moment,
    just removes utm_* query params.

    TODO: Special case normalization for major sites (e.g. youtube)?
    """
    url = urlnorm.norm(resolve(url))
    url_parts = urlparse.urlsplit(url)
    scheme, netloc, path, query, fragment = url_parts

    params = []
    for key, value in cgi.parse_qs(query).iteritems():
        if exclude_param(url_parts, key, value):
            continue
        if isinstance(value, list):
            params.extend((key, v) for v in value)
        else:
            params.append((key, value))

    query = urllib.urlencode(sorted(params), doseq=1)
    return urlparse.urlunsplit((scheme, netloc, path, query, ''))


def exclude_param(url_parts, key, value):
    """Returns True if the given query parameter should be excluded from the
    canonicalized version of a URL.
    """
    if url_parts.netloc.endswith('youtube.com'):
        return key not in ('v', 'p')
    return any(re.match(pattern, key) for pattern in EXCLUDE_PARAM_PATTERNS)


def resolve(url):
    """Resolve any redirects and return the final URL."""
    return requests.head(url, allow_redirects=True).url


def fetch_title(url):
    """Returns the title for the page at the given URL or, if no title is
    found, the URL itself.
    """
    try:
        resp = requests.get(url, stream=True)
        if 'html' in resp.headers.get('Content-Type', ''):
            for chunk in resp.iter_content(2048, decode_unicode=True):
                match = re.search(r'(?iLm)<title>([^<]+)', chunk)
                if match:
                    return match.group(1)
                break
            logging.warn('Title not found in first 2048 bytes of %s', url)
        else:
            logging.warn('Skipping title on non-HTML response: %r', resp.headers.get('Content-Type'))
    except Exception, e:
        logging.exception('Error fetching title for %s: %s', url, e)
    finally:
        resp.close()
    return url


if __name__ == '__main__':
    for line in sys.stdin:
        url = line.strip()
        try:
            print canonicalize(url)
        except requests.TooManyRedirects:
            print 'TOO MANY REDIRECTS: %s' % url
