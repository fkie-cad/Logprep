logprep pseudonymization toolbox
################################

These tools can be used to pseudonymize given strings using the same method as used in Logprep
and provides functionality to depseudonymize values using a pair of keys. 

# preparations
* clone the repository
* make venv with `python3 -m venv .venv` (has to be python3.9 - for mac: `python3.9 -m venv .venv`)
* activate venv with `source .venv/bin/activate` or for powershell `./.venv/bin/Activate.ps1`
* install requirements with `pip install -r requirements.txt`

# usage

## generate keys

```bash
python ./pseudo.py generate -f analyst 1024
python ./pseudo.py generate -f depseudo 2048
```

this will generate four files to pseudonymize in the next step.
the depseudo key has to be longer than the analyst key due to the hash padding involved in the procedure.

* get help with `python ./pseudo.py generate --help`

## pseudonymize

```
python ./pseudo.py pseudonymize analyst depseudo mystring
```
This will pseudonymize the provided string using the analyst and depseudo keys.
* get help with `python ./pseudo.py pseudonymize --help`

## depseudonymize

```
python ./pseudo.py depseudonymize analyst depseudo <output from above>
```
This will depseudonymize the provided string using the analyst and depseudo keys.  
  
* get help with `python ./pseudo.py depseudonymize --help`