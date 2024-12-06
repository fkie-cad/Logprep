""" helper functions for URL extraction and validation.
Code is inspired by django url validation:
https://docs.djangoproject.com/en/4.1/_modules/django/core/validators/
"""

import re
from urllib.parse import urlsplit

valid_schemes = [
    "http",
    "https",
    "ftp",
    "sftp",
    "ssh",
    "file",
    "git",
    "svn",
    "svn+ssh",
    "git+ssh",
    "scp",
    "rsync",
]

ul = "\u00a1-\uffff"  # Unicode letters range (must not be a raw string).

# IP patterns
ipv4_re = (
    r"(?:0|25[0-5]|2[0-4][0-9]|1[0-9]?[0-9]?|[1-9][0-9]?)"
    r"(?:\.(?:0|25[0-5]|2[0-4][0-9]|1[0-9]?[0-9]?|[1-9][0-9]?)){3}"
)
ipv6_re = r"\[[0-9a-f:.]+\]"  # (simple regex, validated later)

# Host patterns
hostname_re = r"[a-z" + ul + r"0-9](?:[a-z" + ul + r"0-9-]+[a-z" + ul + r"0-9])?"

domain_re = r"(?:\.(?!-)[a-z" + ul + r"0-9-]+(?<!-))*"
tld_re = (
    r"\."  # dot
    r"(?!-)"  # can't start with a dash
    r"(?:[a-z" + ul + "-]{2,63}"  # domain label
    r"|xn--[a-z0-9]{1,59})"  # or punycode label
    r"(?<!-)"  # can't end with a dash
    r"\.?"  # may have a trailing dot
)
host_re = rf"{hostname_re}{domain_re}{tld_re}"

url_pattern = re.compile(
    r"(?:(?:[a-z0-9.+-]*)://)?"  # scheme is validated separately
    r"(?:[^\s:@/]+(?::[^\s:@/]*)?@)?"  # user:pass authentication
    r"(?:" + ipv4_re + "|" + ipv6_re + "|" + host_re + ")"
    r"(?::[0-9]{1,5})?"  # port
    r"(?:[/?#][^\s]*)?",  # resource path
    re.IGNORECASE,
)


def extract_urls(field_value: str) -> list:
    """
    Extracts URLs from a given string.

    Parameters
    ----------
    field_value: str
        The field value from which URLs should be extracted.

    Returns
    -------
    list
        A list of URLs extracted from the field value.
    """
    matches = url_pattern.findall(field_value)
    return list(filter(is_valid_url, matches))


def is_valid_url(value: str) -> bool:
    """
    Filters out invalid URLs.

    Parameters
    ----------
    value: str
        The URL to be checked.

    Returns
    -------
    bool
        True if the URL is valid, False otherwise.
    """
    if not is_valid_scheme(value):
        return False
    # Then check full URL
    try:
        if "://" not in value:
            value = "http://" + value
        splitted_url = urlsplit(value)
    except ValueError:
        return False

    # The maximum length of a full host name is 253 characters per RFC 1034
    # section 3.1. It's defined to be 255 bytes or less, but this includes
    # one byte for the length of the name and one byte for the trailing dot
    # that's used to indicate absolute names in DNS.
    if splitted_url.hostname is None or len(splitted_url.hostname) > 253:
        return False

    # Max length for domain name labels is 63 characters per RFC 1034 sec. 3.1
    domain_labels = splitted_url.hostname.split(".")
    if any(len(label) > 63 for label in domain_labels):
        return False

    return True


def is_valid_scheme(value: str) -> bool:
    """
    Filters out invalid URL schemes.

    Parameters
    ----------
    value: str
        The URL scheme to be checked.

    Returns
    -------
    bool
        True if the scheme is valid, False otherwise.
    """

    if "://" not in value:
        return True
    scheme = value.split("://")[0].lower()
    return scheme in valid_schemes


class Domain:
    """Domain object for easy access to domain parts."""

    def __init__(self, domain_string: str):
        if "://" in domain_string:
            self.fqdn = urlsplit(domain_string).hostname
        else:
            self.fqdn = domain_string
        splitted_domain = self.fqdn.split(".")
        self.subdomain = ".".join(splitted_domain[:-2])
        self.domain = splitted_domain[-2]
        self.suffix = splitted_domain[-1]

    def __repr__(self):
        return f"{self.subdomain}.{self.domain}.{self.suffix}"
