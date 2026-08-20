commands used so far to setup 

## activate env 
python -m venv .venv
.\.venv\Scripts\Activate.ps1

## install requirements ( make sure to use python -m to install into venv)
python -m pip install -r requirements.txt

## run tests 
pytest tests/test_config.py -v