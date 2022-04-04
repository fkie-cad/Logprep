import collections
from collections import defaultdict

import pytest

pytest.importorskip("logprep.processor.clusterer")

from logprep.processor.clusterer.signature_calculation.signature_phase import (
    LogRecord,
    SignatureEngine,
    SignatureTagParser,
    SignatureAggregator,
    SignaturePhaseStreaming,
)
from tests.testdata.unit.clusterer.test_data import (
    LogSaltModeTestComposition,
    DatasetSignatureProcessing,
)


class TestSignatureEngine:
    signature_rules = LogSaltModeTestComposition

    log_record = LogRecord(raw_text=DatasetSignatureProcessing.test_record_1.raw_text)

    expected_record = LogRecord(
        raw_text=DatasetSignatureProcessing.test_record_1.raw_text,
        sig_text=DatasetSignatureProcessing.test_record_1.sig_text,
        sig_list=DatasetSignatureProcessing.test_record_1.sig_list,
        sig_str=DatasetSignatureProcessing.test_record_1.sig_str_brackets,
    )

    def test_run(self):
        se = SignatureEngine()
        assert se.run(self.log_record, LogSaltModeTestComposition.rules) == self.expected_record

    def test_apply_signature_engine(self):
        se = SignatureEngine()
        assert (
            se._apply_signature_rules(self.log_record.raw_text, LogSaltModeTestComposition.rules)
            == self.expected_record.sig_text
        )

    @staticmethod
    def test_exception_if_raw_text_with_start_tag():
        raw_text = "Test log with start tag <+> must raise an exception"
        se = SignatureEngine()
        with pytest.raises(BaseException):
            se._apply_signature_rules(raw_text)

    @staticmethod
    def test_exception_if_raw_text_with_end_tag():
        raw_text = "Test log with end tag </+> must raise an exception"
        se = SignatureEngine()
        with pytest.raises(BaseException):
            se._apply_signature_rules(raw_text)

    @staticmethod
    def test_missing_end_tag_in_sig_text():
        sig_text = (
            "Test log with a start tag <+>, but a missing end tag, " "must raise an exception"
        )
        stp = SignatureTagParser()
        with pytest.raises(BaseException):
            stp.calculate_signature(sig_text)


class TestSignatureTagParser:
    sig_text = DatasetSignatureProcessing.test_record_1.sig_text
    expected_signature = DatasetSignatureProcessing.test_record_1.sig_list
    expected_sig_token_pos_list = DatasetSignatureProcessing.test_record_1.sig_token_pos_list

    def test_calculate_signature_engine(self):
        stp = SignatureTagParser()
        assert stp.calculate_signature(self.sig_text) == self.expected_signature

    def test_calculate_signature_positions(self):
        stp = SignatureTagParser()
        assert stp._calculate_signature_positions(self.sig_text) == self.expected_sig_token_pos_list


class TestSignatureAggregator:
    record_1 = LogRecord(signature_str="signature42", number=1)
    log_record_2 = LogRecord(signature_str="signature42", number=2)
    record_3 = LogRecord(signature_str="signature50", number=3)

    def test_logs_with_equal_signature_in_same_bucket(self):
        records = [self.record_1, self.log_record_2]
        expected_mapping_sig_log_nr = defaultdict(list)
        expected_mapping_sig_log_nr[self.record_1.sig_str].append(self.record_1.number)
        expected_mapping_sig_log_nr[self.log_record_2.sig_str].append(self.log_record_2.number)
        sa = SignatureAggregator()
        mapping_signature_lognumber = None
        for record in records:
            mapping_signature_lognumber, _ = sa.run(record)
        assert mapping_signature_lognumber == expected_mapping_sig_log_nr

    def test_logs_with_different_signatures_in_different_buckets(self):
        records = [self.record_1, self.record_3]
        expected_mapping_sig_log_nr = defaultdict(list)
        expected_mapping_sig_log_nr[self.record_1.sig_str].append(self.record_1.number)
        expected_mapping_sig_log_nr[self.record_3.sig_str].append(self.record_3.number)
        expected_mapping_sig_log_nr = collections.OrderedDict(
            sorted(expected_mapping_sig_log_nr.items())
        )
        sa = SignatureAggregator()
        mapping_sig_lognumber = None
        for log_record in records:
            mapping_sig_lognumber, _ = sa.run(log_record)
        assert mapping_sig_lognumber == expected_mapping_sig_log_nr


class TestSignaturePhaseStreaming:
    logsalt_mode = LogSaltModeTestComposition
    record = LogRecord(raw_text=DatasetSignatureProcessing.test_record_1.raw_text)
    expected_log_sig = DatasetSignatureProcessing.test_record_1.sig_str_no_tags

    def test_run_log_cluster_streaming(self):
        sps = SignaturePhaseStreaming()
        sig_str_no_tags = sps.run(self.record, LogSaltModeTestComposition.rules)
        assert sig_str_no_tags == self.expected_log_sig
