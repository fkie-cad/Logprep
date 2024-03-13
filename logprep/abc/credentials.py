"""Abstract Base Class for Credentials"""

import logging
from abc import ABC, abstractmethod

from attrs import define, field, validators
from requests import HTTPError, Session
