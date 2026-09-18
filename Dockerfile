FROM python:3.11-slim

WORKDIR /app

# System deps for matplotlib's Agg backend (no GUI libs needed) are already
# satisfied by the slim image; no extra apt packages required.

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY src ./src
COPY examples ./examples

RUN pip install --no-cache-dir -e .

# Default: run the CLI against the bundled 500-camera/20-site example and
# write the report to /app/report.html. Override the command to run the
# web form instead, e.g.:
#   docker run -p 8000:8000 <image> uvicorn planner.webform:app --host 0.0.0.0 --port 8000
ENTRYPOINT ["python", "-m", "planner"]
CMD ["plan", "--config", "examples/500_cameras_20_sites.yaml", "--out", "report.html"]
