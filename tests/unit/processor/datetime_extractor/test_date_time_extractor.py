from logging import getLogger

import pytest

pytest.importorskip('logprep.processor.datetime_extractor')

from datetime import datetime
from dateutil.tz import tzlocal, tzutc

from logprep.processor.datetime_extractor.factory import DateTimeExtractorFactory
from logprep.processor.datetime_extractor.processor import DateTimeExtractor

logger = getLogger()
rules_dir = 'tests/testdata/unit/datetime_extractor/rules'


@pytest.fixture()
def datetime_extractor():
    config = {
        'type': 'datetime_extractor',
        'rules': [rules_dir],
        'tree_config': 'tests/testdata/unit/shared_data/tree_config.json'
    }

    datetime_extractor = DateTimeExtractorFactory.create('test-datetime-extractor', config, logger)
    return datetime_extractor


class TestDateTimeExtractor:
    def test_an_event_extracted_datetime_utc(self, datetime_extractor):
        assert datetime_extractor.events_processed_count() == 0
        timestamp = '2019-07-30T14:37:42.861Z'
        document = {'@timestamp': timestamp, 'winlog': {'event_id': 123}}

        datetime_extractor.process(document)

        tz_local_name = datetime.now(tzlocal()).strftime('%z')
        local_hour_delta, local_minute_delta, local_timezone = self._parse_local_tz(tz_local_name)

        expected = {'@timestamp': timestamp,
                    'winlog': {'event_id': 123},
                    'split_@timestamp': {
                        'day': 30,
                        'hour': 14 + local_hour_delta,
                        'microsecond': 861000,
                        'minute': 37 + local_minute_delta,
                        'month': 7,
                        'second': 42,
                        'timezone': local_timezone,
                        'weekday': 'Tuesday',
                        'year': 2019}}
        assert document == expected

    def test_an_event_extracted_datetime_plus_one(self, datetime_extractor):
        assert datetime_extractor.events_processed_count() == 0

        timestamp = f'2019-07-30T14:37:42.861+01:00'
        document = {'@timestamp': timestamp, 'winlog': {'event_id': 123}}

        datetime_extractor.process(document)

        tz_local_name = datetime.now(tzlocal()).strftime('%z')
        local_hour_delta, local_minute_delta, local_timezone = self._parse_local_tz(tz_local_name)

        expected = {'@timestamp': timestamp,
                    'winlog': {'event_id': 123},
                    'split_@timestamp': {
                        'day': 30,
                        'hour': 13 + local_hour_delta,  # 13 ist hour of src timestamp in UTC
                        'microsecond': 861000,
                        'minute': 37 + local_minute_delta,
                        'month': 7,
                        'second': 42,
                        'timezone': local_timezone,
                        'weekday': 'Tuesday',
                        'year': 2019}}
        assert document == expected

    def test_an_event_extracted_datetime_and_local_utc_without_delta(self, datetime_extractor):
        assert datetime_extractor.events_processed_count() == 0

        datetime_extractor._local_timezone = tzutc()
        datetime_extractor._local_timezone_name = DateTimeExtractor._get_timezone_name(datetime_extractor._local_timezone)

        timestamp = f'2019-07-30T14:37:42.861+00:00'
        document = {'@timestamp': timestamp, 'winlog': {'event_id': 123}}

        datetime_extractor.process(document)

        tz_local_name = '+0000'
        local_hour_delta, local_minute_delta, local_timezone = self._parse_local_tz(tz_local_name)

        expected = {'@timestamp': timestamp,
                    'winlog': {'event_id': 123},
                    'split_@timestamp': {
                        'day': 30,
                        'hour': 14 + local_hour_delta,
                        'microsecond': 861000,
                        'minute': 37 + local_minute_delta,
                        'month': 7,
                        'second': 42,
                        'timezone': local_timezone,
                        'weekday': 'Tuesday',
                        'year': 2019}}
        assert document == expected

    @staticmethod
    def _parse_local_tz(tz_local_name):
        sign = tz_local_name[:1]
        hour = tz_local_name[1:-2]
        minute = tz_local_name[3:]
        timezone_utc = f'UTC{sign}{hour}:{minute}' if hour != '00' or minute != '00' else 'UTC'
        return int(f'{sign}{hour}'), int(f'{sign}{minute}'), timezone_utc
