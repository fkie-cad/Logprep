import pytest

from logprep.util.helper import DottedTemplate


@pytest.mark.parametrize(
    "identifier",
    [
        "tenant.id",
        "items.0",
        "items.-1",
        "items.0:2",
        "items.:2",
        "items.::-1",
        r"tenant\.id",
        r"tenant\\\.id",
    ],
)
def test_get_identifiers_supports_field_syntax(identifier):
    template = DottedTemplate("${" + identifier + "}")

    assert template.is_valid()
    assert template.get_identifiers() == [identifier]


@pytest.mark.parametrize(
    "identifier",
    [
        "tenant.id",
        "items.0",
        "items.-1",
        "items.0:2",
        "items.:2",
        "items.::-1",
        r"tenant\.id",
        r"tenant\\\.id",
    ],
)
def test_substitute_supports_field_syntax(identifier):
    template = DottedTemplate("http://localhost/${" + identifier + "}")

    assert template.substitute({identifier: "acme"}) == "http://localhost/acme"


def test_substitute_supports_dotted_identifier():
    template = DottedTemplate("http://localhost/${tenant.id}/${LOGPREP_LIST}")

    result = template.substitute(
        {
            "tenant.id": "acme",
            "LOGPREP_LIST": "users.list",
        }
    )

    assert result == "http://localhost/acme/users.list"


def test_safe_substitute_preserves_missing_dotted_identifier():
    template = DottedTemplate("${tenant.id}")

    assert template.safe_substitute({}) == "${tenant.id}"


@pytest.mark.parametrize(
    "value",
    [
        "${tenant..id}",
        "${tenant.}",
        "${.tenant}",
    ],
)
def test_invalid_dotted_identifiers(value):
    assert not DottedTemplate(value).is_valid()
