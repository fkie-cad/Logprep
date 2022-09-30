from os import listdir

from deepdiff import DeepDiff


class AutoRuleCorpusTester:
    def run(self, data_dir):
        test_cases = self.read_files(data_dir)
        self._execute_in_and_out_deepdiff(test_cases)

    def _execute_in_and_out_deepdiff(self, test_cases):

        for test_case in test_cases:
            ...
            diff = DeepDiff(
                expected_output,
                processed_output,
                ignore_order=True,
                report_repetition=True,
                exclude_regex_paths=[],
            )
            assert not diff, f"Diff not empty: {diff}"

    def _strip_input_file_type(self, filename):
        filename = filename.replace("_in", "")
        filename = filename.replace("_out", "")
        filename = filename.replace("_out_custom", "")
        return filename

    def read_files(self, data_dir):
        file_names = [filename for filename in listdir(data_dir) if filename.endswith(".json")]
        test_cases = {}
        for filename in file_names:
            test_case_name = self._strip_input_file_type(filename)
            if test_case_name not in test_cases:
                test_cases[test_case_name] = {"in": "", "out": "", "custom": ""}
            if "_in.json" in filename:
                test_cases[test_case_name]["in"] = filename
            if "_out.json" in filename:
                test_cases[test_case_name]["out"] = filename
            if "_out_custom.json" in filename:
                test_cases[test_case_name]["custom"] = filename
        return test_cases
