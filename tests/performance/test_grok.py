# pylint: disable=missing-docstring
# pylint: disable=protected-access
import timeit

setup_import = """
from unittest import mock

from logprep.factory import Factory
from logprep.processor.grokker.processor import Grokker
from logprep.processor.grokker.rule import GrokkerRule
"""
setup_grokker = """
rule = GrokkerRule._create_from_dict(rule)
grokker_config = {
    "mygrokker": {
        "type": "grokker",
        "specific_rules": [],
        "generic_rules": [],
    }
}
mock_logger = mock.MagicMock()
grokker: Grokker = Factory.create(grokker_config, mock_logger)
grokker._specific_tree.add_rule(rule)
grokker.setup()
"""
run = """
grokker.process(document)
    """

simple_grok_pattern = """
document = {"message": "2020-07-16T19:20:30.45+01:00 DEBUG This is a sample log"}
rule = {
    "filter": "message",
    "grokker": {
        "mapping": {
            "message": "%{TIMESTAMP_ISO8601:@timestamp} %{LOGLEVEL:logLevel} %{GREEDYDATA:logMessage}"
        }
    },
}
"""

linux_syslogline_pattern = """
document = {"message": 'Oct  7 09:21:35 dev-machine c6182927c772[1115]: logger=infra.usagestats t=2023-10-07T09:21:35.676177822Z level=info msg="Usage stats are ready to report"'}
rule = {
    "filter": "message",
    "grokker": {
        "mapping": {
            "message": "%{SYSLOGLINE}"
        }
    },
}
"""

linux_syslogline_5424_pattern = """
document = {"message": 'Oct  7 09:21:35 dev-machine c6182927c772[1115]: logger=infra.usagestats t=2023-10-07T09:21:35.676177822Z level=info msg="Usage stats are ready to report"'}
rule = {
    "filter": "message",
    "grokker": {
        "mapping": {
            "message": "%{SYSLOG5424LINE}"
        }
    },
}
"""


def main():
    testcases = [
        simple_grok_pattern,
        linux_syslogline_pattern,
        linux_syslogline_5424_pattern,
    ]

    for case in testcases:
        print(timeit.timeit(run, number=100000, setup=setup_import + case + setup_grokker))


if __name__ == "__main__":
    main()
