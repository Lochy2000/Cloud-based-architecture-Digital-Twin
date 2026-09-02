commands used so far to setup 

## activate env 
python -m venv .venv
.\.venv\Scripts\Activate.ps1

## install requirements ( make sure to use python -m to install into venv)
python -m pip install -r requirements.txt

### run full stack
docker compose --env-file ../config/env/c1.env --profile c1 up --build                                                               
### Check service state
docker compose --env-file ../config/env/c1.env --profile c1 ps
### Follow logs
docker compose --env-file ../config/env/c1.env --profile c1 logs -f
### Follow only application logs
docker compose --env-file ../config/env/c1.env --profile c1 logs -f publisher storage-writer

### Stop the stack while retaining stored data
docker compose --env-file ../config/env/c1.env --profile c1 down

## run tests 
pytest tests/test_file.py -v
### run all tests
pytest -q