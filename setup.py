from setuptools import setup, find_packages

setup(
    name='logprep',
    version='1.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'logprep = logprep.run_logprep:main',
         ]
    }
)
