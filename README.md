# ERP Backend

A minimal FastAPI backend.

## Requirements

- Python 3.10 or newer
- pip (included with most Python installations)

Check that Python and pip are available:

```powershell
python --version
python -m pip --version
```

## Set up and run on Windows (PowerShell)

Run these commands from the backend directory:

```powershell
# Create a virtual environment
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Start the development server
python -m uvicorn main:app --reload
```

If PowerShell blocks activation because of the execution policy, activate the
environment for the current terminal session and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

You can also run the server without activating the environment:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

The backend runs at <http://127.0.0.1:8000>. Stop it with `Ctrl+C`.

## API documentation

FastAPI generates interactive API documentation automatically:

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>

The starter endpoint is `GET /`, which returns a JSON status message.

## Run on macOS or Linux

From the backend directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

## Deactivate the virtual environment

When finished, run:

```text
deactivate
```
