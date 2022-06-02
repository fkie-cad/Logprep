# pylint: disable=missing-module-docstring
from setuptools import setup, find_packages

import versioneer

with open("requirements.txt", encoding="utf-8") as f:
    requirements = f.read().splitlines()
    requirements = [requirement for requirement in requirements if not requirement.startswith("#")]

setup(
    name="logprep",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="Logprep allows to collect, process and forward log messages from various data "
    "sources.",
    url="https://github.com/fkie-cad/Logprep",
    author="Logprep Team",
    license="LGPL-2.1 license",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    project_urls={
        "Homepage": "https://github.com/fkie-cad/Logprep",
        "Documentation": "https://logprep.readthedocs.io/en/latest/",
    },
    packages=find_packages(),
    install_requires=["setuptools"] + requirements,
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "logprep = logprep.run_logprep:main",
        ]
    },
)
