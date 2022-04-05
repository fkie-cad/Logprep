from os.path import split, join

path_to_testdata = split(__file__)[0]

path_to_schema = join(path_to_testdata, "unit/labeler/schemas/schema.json")
path_to_schema2 = join(path_to_testdata, "unit/labeler/schemas/schema2.json")

path_to_rules = join(path_to_testdata, "unit/labeler/test_only_rules")
path_to_rules2 = join(path_to_testdata, "unit/labeler/test_only_rules2")
path_to_invalid_rules = join(path_to_testdata, "unit/labeler/rules_invalid", "rules")
path_to_single_rule = join(path_to_rules, "single")

path_to_config = join(path_to_testdata, "config/config.yml")
path_to_alternative_config = join(path_to_testdata, "config/config2.yml")
path_to_invalid_config = join(path_to_testdata, "config/config-invalid.yml")
