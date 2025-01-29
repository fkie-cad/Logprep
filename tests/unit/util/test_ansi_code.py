from logprep.util.ansi import Fore, Back


class TestAnsiCodes:
    def test_basic_color_codes(self):
        assert Fore.BLACK == "\033[30m"
        assert Fore.RED == "\033[31m"
        assert Fore.GREEN == "\033[32m"
        assert Fore.YELLOW == "\033[33m"
        assert Fore.BLUE == "\033[34m"
        assert Fore.MAGENTA == "\033[35m"
        assert Fore.CYAN == "\033[36m"
        assert Fore.WHITE == "\033[37m"
        assert Fore.RESET == "\033[39m"
        assert Back.BLACK == "\033[40m"
        assert Back.YELLOW == "\033[43m"
        assert Back.MAGENTA == "\033[45m"
        assert Back.CYAN == "\033[46m"
        assert Back.WHITE == "\033[47m"
        assert Back.RESET == "\033[49m"
