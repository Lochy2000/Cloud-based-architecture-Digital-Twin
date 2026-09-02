# Local quick start

Commands use Windows PowerShell and assume the repository root is current.

## Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
### move into deploy folder
cd deploy
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