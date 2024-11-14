# Contributing

Every contribution is highly appreciated.
If you have ideas or improvements feel free to create a fork and open a pull requests.
Issues and engagement in open discussions are also welcome.

## Developers

### Languages
* We use python3 for rapid prototyping and fast development cycles.
* We started with rust for performance improvements.

### Tests
* We write unit tests for our code.
* We use pytest for tests.
* We use pylint to check test coverage. We aim for a coverage of 100%. However, even 100% coverage does not guarantee that everything was fully tested.
* Every fixed bug should have its own unittest.
* We write unittests in rust for rust code.
* We write integration tests for python for every exposed interface from rust.

### Git Workflow
* We have a main branch. We do not push to the main branch, please develop on a separate branch and open a pull request to main.
* We create pull requests in GitHub to merge a branch into main. A maintainer must accept each request.
* Branches should be named after the feature/fix that they implement. Words should be separated by hyphens. Feature branches should begin with 'dev-' and fix branches with 'fix-' (e.g. 'dev-kafka-connector') or you go with the auto generated branch names from github.
* The main branch must always be in a functioning state, i.e., all tests pass successfully.
* We merge  pull requests with "Squash and merge".
* New commits must pass the unit tests.
* Rebasing feature branches, e.g., to clean up the git history, is strongly advised before request a review.

### Commit Messages
* We divide subject and content with a blank line.
* The subject should not be longer than 50 characters, but 72 is the maximum limit.
* The subject should begin with a capital letter.
* The subject should not end with a period.
* We write commit messages in English.
* The subject should complete the sentence "If applied, this commit will ..." (e.g., "If applied, this commit will ‘Add some functionality‘").
* A subject is mandatory, but content is not.
* The content should have line breaks after 72 characters.
* The content should describe what was done and why it was done, but not how it was done.

### Pre-Commit Hooks
* We use pre-commit hooks to sanitize files before commiting
* Install the pre-commit hooks with `pre-commit install` in the root directory

### Pull Request and Definition of Done
* draft a Pull Request as soon as possible to signal your commitment.
* write a clear description of what a maintainer have to expect from your PR.
* add an entry in the [CHANGELOG.md](https://github.com/fkie-cad/Logprep/blob/main/CHANGELOG.md) file for your feature, improvement or bugfix.
* add the needed documentation in the docs.
* add tests for your work.
* ensure all tests run.
* if you have done all of the above, add a maintainer for review and mark your PR as ready.

### Deprecations
* If a function or features gets deprecated a warning should be logged with `logger.warning`. The message should start with `[Deprecation]:` and end with an indication when this deprecation will expire, e.g.: `[Expires with logprep=4.0.0]`.
* Furthermore, the corresponding code parts should be marked with a comment starting like `# DEPRECATION: <SHORT-Name> <Comment>`. This way it is later easy to find again the lines of code that have to be revised before the deprecation will be fully removed.
* The [CHANGELOG.md](https://github.com/fkie-cad/Logprep/blob/main/CHANGELOG.md) should be updated such that the next release contains a remark that a feature will be marked as deprecated and indicating in the `Upcoming Changes` section that the deprecation will also be removed in the future.

### Code Quality and Style
* We adhere to PEP-8.
* We use pylint to check the code quality. We aim for a code quality of at least 9.5 for production code.
* We use [`black`](https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html) as formater.
* Exceptions: We use a line length of max. 100 characters and reduce the min. public methods expected by pylint from two to one.
* We explicitly suppress pylint (via flags) for code parts where we do not agree with pylint.
* Tests require no docstrings.
* We use Python type hints.

### Documentation
* We use Sphinx to document the code.
* We update the documentation for every change or addition of a feature.
* We write docstrings for production code and adhere to PEP-257 and the Numpy style.
* We start multiline docstrings in the first line after the quotation marks instead of the second line (both options are equivalent).
* We track changes in a [CHANGELOG.md](https://github.com/fkie-cad/Logprep/blob/main/CHANGELOG.md) and communicate deprecations in it.

### Issues in GitHub
* We create issues on demand. We assign issues only after personally agreeing on it with the assignee.

## Maintainers

### Release Workflow
* Prerequisite: It was checked that communicated upcoming changes were actually done, e.g deprecations that should be removed with a major release were actually removed.
* Before we make a new release we update the [CHANGELOG.md](https://github.com/fkie-cad/Logprep/blob/main/CHANGELOG.md)
There we rename the section `next release` to the version that will be released and add a new section `next release`.
This section is continuously updated during the development of the next release.
* Once this update is pushed and merged we tag a new release in git, prefixed with `v`, resulting in a tag like `v2.0.1`.
We adhere to the [SemVer](https://semver.org/) Specifications.
* Once the tag is pushed we create a release in GitHub. The release description should contain the changes documented
in the [CHANGELOG.md](https://github.com/fkie-cad/Logprep/blob/main/CHANGELOG.md).
* A configured GitHub Action then takes this published release and automatically uploads a new build to [PyPI Logprep](https://pypi.org/project/logprep/).

### Helm Chart Release Workflow

* To release a new helm chart we update the versions in the [Chart.yaml](https://github.com/fkie-cad/Logprep/blob/main/charts/logprep/Chart.yaml) in a feature branch.
* Then we merge this change to the main branch.
* There a pipeline packages the helm chart and makes the actual helm chart release on the release page.
