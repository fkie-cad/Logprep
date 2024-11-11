"""This module contains classes for misuse detection and rule attribution
as used by AMIDES."""

from typing import Dict, List, Tuple

from sklearn.base import BaseEstimator
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler

from logprep.processor.amides.features import CommaSeparation


class DetectionModelError(Exception):
    """Base exception class for all RuleModel-related errors."""


class MissingModelComponentError(DetectionModelError):
    """Raised if required model component could not be loaded."""

    def __init__(self, name: str):
        super().__init__(f"Model component {name} is missing or uses different key")


class DetectionModel:
    """DetectionModel combines vectorizer fitted used taining data and classifier
    trained on same data to detect malicious data samples."""

    __slots__ = ("_clf", "_vectorizer", "_scaler")

    _clf: BaseEstimator
    _vectorizer: TfidfVectorizer
    _scaler: MinMaxScaler

    def __init__(self, misuse_model: dict):
        self._setup(misuse_model)

    def _setup(self, model: dict):
        try:
            self._clf = model["clf"]
            self._vectorizer = model["vectorizer"]
            self._vectorizer.tokenizer = CommaSeparation()
            self._scaler = model["scaler"]
        except KeyError as err:
            raise MissingModelComponentError(err.args[0]) from err

    def detect(self, sample: str) -> float:
        """Detect malicious data sample. Returns confidence value that estimates how likely
        given sample is malicious.

        Parameters
        ----------
        sample: str
            Sample string to evaluate.

        Returns
        -------
        confidence_value: float
            Value between 0.0 and 1.0 that serves as confidence value.
        """
        feature_vector = self._vectorizer.transform([sample])
        df_value = self._clf.decision_function(feature_vector)
        scaled_df_value = self._scaler.transform(df_value.reshape(-1, 1)).flatten()[0]

        return scaled_df_value.item()


class MisuseDetector(DetectionModel):
    """MisuseDetector as sub-class of DetectionModel allows the definition of a
    decision threshold value to fine-tune from when samples are declared as malicious.
    """

    __slots__ = ("_decision_threshold",)

    _decision_threshold: float

    def __init__(self, misuse_model: dict, decision_threshold: float):
        super().__init__(misuse_model)
        self._decision_threshold = decision_threshold

    def detect(self, sample: str) -> Tuple[bool, float]:
        """Detect if given sample is malicious. Returns 0 or 1 if sample's detection
        result is below or above the configured decision threshold.

        Parameters
        ----------
        sample: str
            Sample string to evaluate.

        Returns
        -------
        predict: Tuple[boolean, float].
            Detection result as boolean value and the corresponding confidence.
        """
        confidence_value = super().detect(sample)

        if confidence_value >= self._decision_threshold:
            return True, round(confidence_value, 3)
        return False, round(confidence_value, 3)


class RuleAttributorError(Exception):
    """Base class for all RuleAttributor-related Errors."""


class RuleAttributor:
    """RuleAttributor attributes malicious samples to misuse detection rules."""

    __slots__ = ("_rule_models", "_num_rule_attributions", "_attribution_threshold")

    _rule_models: Dict[str, DetectionModel]
    _num_rule_attributions: int

    def __init__(
        self,
        rule_models: dict,
        num_rule_attributions: int,
    ):
        self._num_rule_attributions = num_rule_attributions
        self._rule_models = {}

        self._setup(rule_models)

    def _setup(self, models: dict):
        for rule_name, rule_model in models.items():
            try:
                rule_model = DetectionModel(rule_model)
                self._rule_models[rule_name] = rule_model
            except DetectionModelError as err:
                raise RuleAttributorError from err

    def attribute(self, sample: str) -> List[dict]:
        """Attribute given sample to rules of which the attributor holds rule models.

        Parameters
        ----------
        sample: str
            Malicious sample to attribute.

        Returns
        -------
        attributions: List[dict]
            List of rule attributions, containing rule model names and confidence values.
        """
        conf_values = self._calculate_rule_confidence_values(sample)

        return self._get_rules_with_highest_confidence_values(conf_values)

    def _calculate_rule_confidence_values(self, cmdline: str) -> List[dict]:
        conf_values = []

        for name, rule_model in self._rule_models.items():
            rule_confidence_value = rule_model.detect(cmdline)
            conf_values.append({"rule": name, "confidence": round(rule_confidence_value, 3)})

        return conf_values

    def _get_rules_with_highest_confidence_values(self, conf_values: List[dict]) -> List[dict]:
        conf_values.sort(key=lambda item: item["confidence"], reverse=True)

        return conf_values[: self._num_rule_attributions]
