# pylint: disable=missing-docstring
from logprep.util.ansi import BackgroundColor, ForegroundColor


class TestAnsiCodes:
    def test_basic_color_codes(self):
        assert ForegroundColor.BLACK == "\033[30m"
        assert ForegroundColor.RED == "\033[31m"
        assert ForegroundColor.GREEN == "\033[32m"
        assert ForegroundColor.YELLOW == "\033[33m"
        assert ForegroundColor.BLUE == "\033[34m"
        assert ForegroundColor.MAGENTA == "\033[35m"
        assert ForegroundColor.CYAN == "\033[36m"
        assert ForegroundColor.WHITE == "\033[37m"
        assert ForegroundColor.RESET == "\033[39m"
        assert BackgroundColor.BLACK == "\033[40m"
        assert BackgroundColor.YELLOW == "\033[43m"
        assert BackgroundColor.MAGENTA == "\033[45m"
        assert BackgroundColor.CYAN == "\033[46m"
        assert BackgroundColor.WHITE == "\033[47m"
        assert BackgroundColor.RESET == "\033[49m"
