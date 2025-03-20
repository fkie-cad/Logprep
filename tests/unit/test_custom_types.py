import click
import pytest
from click.testing import CliRunner

from logprep.util.custom_types import BoolOrStr


@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        (True, True),
        (False, False),
        ("true", True),
        ("false", False),
        ("TRUE", True),
        ("FALSE", False),
        ("Hello", "Hello"),
        ("123", "123"),
        ("http://example.com", "http://example.com"),
    ],
)
def test_bool_or_str_valid(input_value, expected_output):
    param_type = BoolOrStr()
    assert param_type.convert(input_value, None, None) == expected_output


@pytest.mark.parametrize(
    "invalid_value",
    [
        123,
        12.34,
        None,
        [],
        {},
    ],
)
def test_bool_or_str_invalid(invalid_value):
    param_type = BoolOrStr()
    with pytest.raises(click.BadParameter):
        param_type.convert(invalid_value, None, None)


def test_click_option():
    runner = CliRunner()

    @click.command()
    @click.option("--verify", type=BoolOrStr(), default=True)
    def cli(verify):
        click.echo(f"verify: {verify} (type: {type(verify).__name__})")

    # Test valid cases
    result = runner.invoke(cli, ["--verify", "true"])
    assert result.exit_code == 0
    assert "verify: True (type: bool)" in result.output

    result = runner.invoke(cli, ["--verify", "http://example.com"])
    assert result.exit_code == 0
    assert "verify: http://example.com (type: str)" in result.output

    # Test invalid case
    result = runner.invoke(cli, ["--verify", "123"])
    assert result.exit_code == 0
    assert "verify: 123 (type: str)" in result.output
