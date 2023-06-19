# pylint: disable=missing-docstring
import numpy as np
import pytest
from sklearn.preprocessing import MinMaxScaler

from logprep.processor.amides.detection import (
    MissingModelComponentError,
    MisuseDetector,
    RuleAttributor,
    RuleAttributorError,
)


class MockVectorizer:
    """MockVectorizer to mock vectorizer for testing purposes."""

    def transform(self, sample: str) -> np.array:
        if np.array_equal(sample, np.array(["benign"])):
            return np.array([0, 0.5, 1])

        return np.array([0.5, 1, 0])


class MockClassifier:
    """MockClassifier to mock classifier for testing purposes."""

    def __init__(self, malicious_predict: float = 0.5):
        self._malicious_predict = np.array([malicious_predict])

    def decision_function(self, features: np.array) -> np.array:
        benign = np.array([0, 0.5, 1])

        if np.array_equal(features, benign):
            return np.array([-0.5])
        return self._malicious_predict


class MockScaler:
    """MockScaler to mock scaler for testing purposes."""

    def __init__(self, minimum: float, maximum: float):
        self._scaler = MinMaxScaler()
        self._scaler.fit(np.array([[minimum], [maximum]]))

    def transform(self, values: np.array) -> np.array:
        return self._scaler.transform(values)


@pytest.fixture(name="misuse_model")
def fixture_misuse_model():
    return {
        "clf": MockClassifier(malicious_predict=0.8),
        "vectorizer": MockVectorizer(),
        "scaler": MockScaler(minimum=-0.5, maximum=0.8),
    }


class TestMisuseDetector:
    def test_init(self, misuse_model):
        assert MisuseDetector(misuse_model, decision_threshold=0.5)

    def test_init_missing_vectorizer(self, misuse_model):
        del misuse_model["vectorizer"]

        with pytest.raises(MissingModelComponentError):
            _ = MisuseDetector(misuse_model, decision_threshold=0.5)

    def test_init_missing_scaler(self, misuse_model):
        del misuse_model["scaler"]

        with pytest.raises(MissingModelComponentError):
            _ = MisuseDetector(misuse_model, decision_threshold=0.5)

    def test_init_missing_clf(self, misuse_model):
        del misuse_model["clf"]

        with pytest.raises(MissingModelComponentError):
            _ = MisuseDetector(misuse_model, decision_threshold=0.5)

    def test_detect(self, misuse_model):
        detector = MisuseDetector(misuse_model, 0.5)
        assert detector.detect("benign") == (False, 0.0)
        assert detector.detect("malicious") == (True, 1.0)


class TestRuleAttributor:
    @pytest.fixture
    def rule_models(self):
        return {
            "rule_a": {
                "clf": MockClassifier(malicious_predict=0.6),
                "vectorizer": MockVectorizer(),
                "scaler": MockScaler(minimum=-1.0, maximum=1.0),
            },
            "rule_b": {
                "clf": MockClassifier(malicious_predict=0.4),
                "vectorizer": MockVectorizer(),
                "scaler": MockScaler(minimum=-1.0, maximum=1.0),
            },
            "rule_c": {
                "clf": MockClassifier(malicious_predict=0.8),
                "vectorizer": MockVectorizer(),
                "scaler": MockScaler(minimum=-1.0, maximum=1.0),
            },
        }

    def test_init(self, rule_models):
        assert RuleAttributor(
            rule_models,
            num_rule_attributions=10,
        )

    def test_init_missing_rule_model_component(self, rule_models):
        del rule_models["rule_a"]["clf"]

        with pytest.raises(RuleAttributorError):
            _ = RuleAttributor(
                rule_models,
                num_rule_attributions=10,
            )

    def test_attribute_malicious_sample_sufficient_number_of_confidence_values(self, rule_models):
        expected = [{"rule": "rule_c", "confidence": 0.9}, {"rule": "rule_a", "confidence": 0.8}]
        attributor = RuleAttributor(
            rule_models,
            num_rule_attributions=2,
        )

        results = attributor.attribute("malicious")
        assert results == expected

    def test_attribute_malicious_sample_too_few_sufficient_confidence_values(self, rule_models):
        expected = [
            {"rule": "rule_c", "confidence": 0.9},
            {"rule": "rule_a", "confidence": 0.8},
            {"rule": "rule_b", "confidence": 0.7},
        ]

        attributor = RuleAttributor(
            rule_models,
            num_rule_attributions=4,
        )

        results = attributor.attribute("malicious")
        assert results == expected
