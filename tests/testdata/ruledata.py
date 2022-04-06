simple_rule_dict = {"filter": 'applyrule: "yes"', "label": {"reporter": ["windows"]}}

null_rule_dict = {"filter": "applyrule: null", "label": {"reporter": ["windows"]}}

simple_regex_rule_dict = {
    "filter": 'applyrule: ".*yes.*"',
    "regex_fields": ["applyrule"],
    "label": {"reporter": ["windows"]},
}

# String of length >= 8 with at least 3 of these: upper-case, lower-case, number, non-alphanumeric
# Simple rules don't cover many possibilities for parsing errors
complex_regex_rule_dict = {
    "filter": r'applyrule: "(?:(?=.*[a-z])(?:(?=.*[A-Z])(?=.*[\d\W])|(?=.*\W)(?=.*\d))|(?=.*\W)(?=.*[A-Z])(?=.*\d)).{8,}"',
    "regex_fields": ["applyrule"],
    "label": {"reporter": ["windows"]},
}

simple_rule = [simple_rule_dict]

simple_regex_rule = [simple_regex_rule_dict]

# String of length >= 8 with at least 3 of these: upper-case, lower-case, number, non-alphanumeric
# Simple rules don't cover many possibilities for parsing errors
complex_regex_rule = [complex_regex_rule_dict]

null_rule = [null_rule_dict]
