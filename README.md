# QuickBite Delivery – standalone service

This is one independent Git repository. Its source and requirements are isolated.

## Local launch (from this directory)
```sh
python -m pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 3003
```
With the full solution, start at repository root using `python run_local.py` or `docker compose up --build -d`.
See root README for upstream URLs, database settings and Kubernetes deployment.

## Independent CI/CD proof
This repository includes `.github/workflows/ci.yml` to run its own pytest checks and Docker image build on push/pull request.
