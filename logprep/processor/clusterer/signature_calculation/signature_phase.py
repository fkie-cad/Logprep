"""Module for Signature-Phase of the Log-Clustering."""

from typing import Tuple, List, Dict

from collections import OrderedDict
from types import SimpleNamespace

from logprep.processor.clusterer.configuration import SignatureProgramTags
from logprep.processor.clusterer.rule import ClustererRule


class LogRecord(SimpleNamespace):
    """Container for raw text and the signature in different states."""

    raw_text = ""
    # str 'Mar 15 00:34:53 combo sshd[11755]: Accepted password for judy55 from
    # 192.168.56.13 port 59405 ssh2'
    sig_text = ""
    # str '(...) <+>sshd</+> <+>Failed</+> (...) judy55 ssh2'
    sig_list = ""
    # list ['<+>sshd</+>', '<+>Failed</+>', (...)]
    sig_str = ""
    # str '<+>sshd</+> <+>Failed</+> (...)'
    sig_str_no_tags = ""
    # str 'sshd Failed'


class SignaturePhaseStreaming:
    """Responsible for clustering a log by calculating the cluster signature."""

    def __init__(self):
        self._se = SignatureEngine()

    def run(self, record: LogRecord, rules: List[ClustererRule]) -> str:
        """Process a log event by calculating the cluster signature."""
        record = self._se.run(record, rules)
        record.sig_str_no_tags = self._remove_tags(record.sig_str)
        return record.sig_str_no_tags

    @staticmethod
    def _remove_tags(sig_str: str) -> str:
        """Remove the tag respectively markup signs."""
        sig_str_no_tags = sig_str.replace(SignatureProgramTags.start_tag, "").replace(
            SignatureProgramTags.end_tag, ""
        )
        return sig_str_no_tags


class SignatureEngine:
    """Calculates Signatures."""

    def __init__(self):
        self._sp = SignatureTagParser()

    def run(self, record: LogRecord, rules: List[ClustererRule]) -> LogRecord:
        """Run the signature engine."""
        record.sig_text = self._apply_signature_rules(record.raw_text, rules)
        record.sig_list = self._sp.calculate_signature(record.sig_text)
        record.sig_str = " ".join(record.sig_list)
        return record

    def _apply_signature_rules(self, raw_text: str, rules: List[ClustererRule]) -> str:
        self._sp.check_no_start_and_end_tag_in_raw_text(raw_text)
        sig_text = raw_text
        for rule in rules:
            sig_text = self.apply_signature_rule(rule, sig_text)
        return sig_text

    @staticmethod
    def apply_signature_rule(rule: ClustererRule, sig_text: str) -> str:
        """Apply a signature rule to a string based on a matching and a replacement pattern.

        This function substitutes regEx matches in a string based on patterns defined in rules to
        generate a clusterer signature. The result can be an intermediate step in the generation of
        a signature as part of a sequence of clusterer rules.

        The substitution is performed repeatedly on the same string until it doesn't match anymore.
        To ensure that there is never an endless loop of substitutions, the loop breaks if the
        number of performed substitutions doesn't decrease with each iteration.

        Parameters
        ----------
        rule: ClustererRule
            Rule containing replacement and substitution pattern.
        sig_text: str
            Text that is used to generate a signature from.

        Returns
        -------
        str
            Signature generated from input text.

            This doesn't have to be a final signature, but can be an intermediate result.

        """
        sig_text, num_of_subs = rule.pattern.subn(rule.repl, sig_text)
        # last_num_of_subs is set greater than num_of_subs so that it is possible to enter the loop
        last_num_of_subs = num_of_subs + 1
        while 0 < num_of_subs < last_num_of_subs:
            last_num_of_subs = num_of_subs
            sig_text, num_of_subs = rule.pattern.subn(rule.repl, sig_text)
        return sig_text


class SignatureAggregator:
    """
    Aggregate Logs according their cluster signature (key=signature_str, value=log_record Numbers).
    """

    def __init__(self):
        self.sig_to_log_nr_map = {}

    def run(self, record: LogRecord) -> Tuple[Dict[str, List[int]], None]:
        """Run the signature aggregator."""
        if record.sig_str in self.sig_to_log_nr_map:
            log_list = self.sig_to_log_nr_map[record.sig_str]
            log_list.append(record.number)
            self.sig_to_log_nr_map[record.sig_str] = log_list
        else:
            self.sig_to_log_nr_map[record.sig_str] = [record.number]
        self.sig_to_log_nr_map = self._sort_dictionary(self.sig_to_log_nr_map)
        return self.sig_to_log_nr_map, None

    @staticmethod
    def _sort_dictionary(sig_to_log_nr_map: dict) -> OrderedDict:
        sorted_sig_to_log_nr_map = OrderedDict(sorted(sig_to_log_nr_map.items()))
        return sorted_sig_to_log_nr_map


class SignatureTagParser:
    """Signature Tag Parser (Helper Class for Signature Engine)."""

    default_start_tag = SignatureProgramTags.start_tag
    default_end_tag = SignatureProgramTags.end_tag

    def __init__(self, start_tag: str = None, end_tag: str = None):
        self.start_tag = start_tag or self.default_start_tag
        self.end_tag = end_tag or self.default_end_tag

    def calculate_signature(self, sig_text: str) -> List[str]:
        """Calculate the cluster signature."""
        sig_pos_list = self._calculate_signature_positions(sig_text)
        sig_list = []
        for sig_pos in sig_pos_list:
            signature = sig_text[sig_pos[0] : sig_pos[1]]
            sig_list.append(signature)
        return sig_list

    def _calculate_signature_positions(self, sig_text: str) -> List[List[int]]:
        cursor = 0
        sig_token_pos = []
        while True:
            start_pos = sig_text[cursor:].find(self.start_tag)
            if start_pos == -1:
                break
            sig_token_start = cursor + start_pos
            cursor = cursor + start_pos + len(self.start_tag)
            end_pos = sig_text[cursor:].find(self.end_tag)
            if end_pos == -1:
                raise Exception(f"ERROR: invalid grammatic, missing {self.end_tag} tag")
            sig_token_end = cursor + end_pos + len(self.end_tag)
            sig_token_pos.append([sig_token_start, sig_token_end])
        return sig_token_pos

    def check_no_start_and_end_tag_in_raw_text(self, raw_text: str):
        """Check if the start and end tags are in the raw text."""
        if self.start_tag in raw_text:
            raise Exception(f"ERROR: Start-tag {self.start_tag} in raw log message")
        if self.end_tag in raw_text:
            raise Exception(f"ERROR: End-tag {self.end_tag} in raw log message")
