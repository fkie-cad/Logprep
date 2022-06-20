# pylint: disable=missing-module-docstring
from setuptools import setup, find_packages
import versioneer

setup(
    name="logprep",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    packages=find_packages(),
    install_requires=["setuptools"],
    entry_points={
        "console_scripts": [
            "logprep = logprep.run_logprep:main",
        ]
    },
)
