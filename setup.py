from setuptools import setup, find_packages

setup(
    name='logprep',
    version='0.1',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'logprep = logprep.run_logprep:main',
         ]
    }
)

