from datetime import datetime

import ciso8601
import pendulum


def parse_timestamp(source: str) -> datetime:
    try:
        return ciso8601.parse_datetime(source)
    except ValueError:
        return pendulum.parse(source, strict=False)
