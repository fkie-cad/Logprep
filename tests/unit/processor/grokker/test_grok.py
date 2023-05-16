# pylint: disable=missing-docstring
from logprep.util.grok.grok import Grok


def test_one_pat():
    text = "1024"
    pat = "%{INT:test_int}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match["test_int"] == "1024", f"grok match failed: {text}, {pat}"


def test_one_pat_1():
    text = "1024"
    pat = "%{NUMBER:test_num}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match["test_num"] == "1024", f"grok match failed: {text}, {pat}"


def test_one_pat_2():
    text = "garyelephant "
    pat = "%{WORD:name} "
    grok = Grok(pat)
    match = grok.match(text)
    assert match["name"] == text.strip(), f"grok match failed: {text}, {pat}"


def test_one_pat_3():
    text = "192.168.1.1"
    pat = "%{IP:ip}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match["ip"] == text.strip(), f"grok match failed:{text}, {pat}"


def test_one_pat_4():
    text = "github.com"
    pat = "%{HOSTNAME:website}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match["website"] == text.strip(), f"grok match failed: {text}, {pat}"


def test_one_pat_5():
    text = "1989-11-04 05:33:02+0800"
    pat = "%{TIMESTAMP_ISO8601:ts}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match["ts"] == text.strip(), f"grok match failed: {text}, {pat}"


def test_one_pat_6():
    text = "github"
    pat = "%{WORD}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match == {}, f"grok match failed: {text}, {pat}"
    # you get nothing because variable name is not set,
    # compare "%{WORD}" and "%{WORD:variable_name}"


def test_one_pat_7():
    text = "github"
    pat = "%{NUMBER:test_num}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match == {}, f"grok match failed: {text}, {pat}"
    # not match


def test_one_pat_8():
    text = "1989"
    pat = "%{NUMBER:birthyear:int}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match == {"birthyear": 1989}, f"grok match failed:{text}, {pat}"


def test_multiple_pats():
    text = 'gary 25 "never quit"'
    pat = "%{WORD:name} %{INT:age} %{QUOTEDSTRING:motto}"
    grok = Grok(pat)
    match = grok.match(text)
    assert (
        match["name"] == "gary" and match["age"] == "25" and match["motto"] == '"never quit"'
    ), f"grok match failed:{text}, {pat}"

    # variable names are not set
    text = 'gary 25 "never quit"'
    pat = "%{WORD} %{INT} %{QUOTEDSTRING}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match == {}, f"grok match failed:{text}, {pat}"

    # "male" is not INT
    text = 'gary male "never quit"'
    pat = "%{WORD:name} %{INT:age} %{QUOTEDSTRING:motto}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match == {}, f"grok match failed:{text}, {pat}"

    # nginx log
    text = (
        "edge.v.iask.com.edge.sinastorage.com 14.18.243.65 6.032s - [21/Jul/2014:16:00:02 +0800]"
        + ' "GET /edge.v.iask.com/125880034.hlv HTTP/1.0" 200 70528990 "-"'
        + ' "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)'
        + ' Chrome/36.0.1985.125 Safari/537.36"'
    )
    pat = (
        r"%{HOSTNAME:host} %{IP:client_ip} %{NUMBER:delay}s - \[%{DATA:time_stamp}\]"
        r' "%{WORD:verb} %{URIPATHPARAM:uri_path} HTTP/%{NUMBER:http_ver}" '
        r"%{INT:http_status} %{INT:bytes} %{QS} %{QS:client}"
    )
    grok = Grok(pat)
    match = grok.match(text)
    assert (
        match["host"] == "edge.v.iask.com.edge.sinastorage.com"
        and match["client_ip"] == "14.18.243.65"
        and match["delay"] == "6.032"
        and match["time_stamp"] == "21/Jul/2014:16:00:02 +0800"
        and match["verb"] == "GET"
        and match["uri_path"] == "/edge.v.iask.com/125880034.hlv"
        and match["http_ver"] == "1.0"
        and match["http_status"] == "200"
        and match["bytes"] == "70528990"
        and match["client"]
        == '"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)'
        + ' Chrome/36.0.1985.125 Safari/537.36"'
    ), f"grok match failed:{text}, {pat}"

    text = "1989/02/23"
    pat = "%{NUMBER:birthyear:int}/%{NUMBER:birthmonth:int}/%{NUMBER:birthday:int}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match == {
        "birthyear": 1989,
        "birthmonth": 2,
        "birthday": 23,
    }, f"grok match failed:{text}, {pat}"

    text = "load average: 1.88, 1.73, 1.49"
    pat = "load average: %{NUMBER:load_1:float}, %{NUMBER:load_2:float}, %{NUMBER:load_3:float}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match == {
        "load_1": 1.88,
        "load_2": 1.73,
        "load_3": 1.49,
    }, f"grok match failed:{text}, {pat}"


def test_custom_pats():
    custom_pats = {"ID": "%{WORD}-%{INT}"}
    text = 'Beijing-1104,gary 25 "never quit"'
    pat = "%{ID:user_id},%{WORD:name} %{INT:age} %{QUOTEDSTRING:motto}"
    grok = Grok(pat, custom_patterns=custom_pats)
    match = grok.match(text)
    assert (
        match["user_id"] == "Beijing-1104"
        and match["name"] == "gary"
        and match["age"] == "25"
        and match["motto"] == '"never quit"'
    ), f"grok match failed:{text}, {pat}"


def test_custom_pat_files():
    pats_dir = "tests/testdata/unit/grokker/patterns"
    text = 'Beijing-1104,gary 25 "never quit"'
    # pattern "ID" is defined in ./test_patterns/pats
    pat = "%{ID:user_id},%{WORD:name} %{INT:age} %{QUOTEDSTRING:motto}"
    grok = Grok(pat, custom_patterns_dir=pats_dir)
    match = grok.match(text)
    assert (
        match["user_id"] == "Beijing-1104"
        and match["name"] == "gary"
        and match["age"] == "25"
        and match["motto"] == '"never quit"'
    ), f"grok match failed:{text}, {pat}"


def test_hotloading_pats():
    text = "github"
    pat = "%{WORD:test_word}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match["test_word"] == "github", f"grok match failed:{text}, {pat}"
    # matches

    text = "1989"
    pat = "%{NUMBER:birthyear:int}"
    grok.set_search_pattern(pat)
    match = grok.match(text)
    assert match == {"birthyear": 1989}, f"grok match failed:{text}, {pat}"


def test_matches_with_deep_field():
    text = "github"
    pat = "%{WORD:[field1][field2]}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match["field1.field2"] == "github", f"grok match failed: {text}, {pat}"


def test_matches_with_deep_field_and_conversion():
    text = "123"
    pat = "%{NUMBER:[field1][field2]:int}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match["field1.field2"] == 123, f"grok match failed: {text}, {pat}"


def test_matches_with_special_characters_in_match_group():
    text = "123"
    pat = "%{NUMBER:@number:int}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match["@number"] == 123, f"grok match failed: {text}, {pat}"


def test_matches_with_plain_oniguruma_syntax():
    text = "123"
    pat = "(?<number>.*)"
    grok = Grok(pat)
    match = grok.match(text)
    assert match["number"] == "123", f"grok match failed: {text}, {pat}"


def test_matches_with_mixed_oniguruma_and_grok_syntax():
    text = "123 456"
    pat = r"(?<number1>\d{3}) %{NUMBER:number2}"
    grok = Grok(pat)
    match = grok.match(text)
    assert match["number1"] == "123", f"grok match failed: {text}, {pat}"
    assert match["number2"] == "456", f"grok match failed: {text}, {pat}"
