# Contributing

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev]"
```

## Test

Run the complete unit test suite from the repository root:

```powershell
python -m unittest
```

## Guidelines

- Keep camera, detector, profile, checkpoint, indicator, and storage responsibilities separated.
- Add focused tests for behavior changes.
- Use mock sources, detectors, and indicators for tests; do not require real hardware.
- Keep runtime data and model artifacts out of source commits.
- Do not add credentials or private worker/video data to the repository.
