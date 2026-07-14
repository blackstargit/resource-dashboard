# Resource Monitoring Backend

Isolated API service for monitoring system resources (CPU, RAM, Disk, GPU).
Designed to be used with the `resource-dashboard` frontend.

## Quick Start (Local)

1. Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the backend:
   ```bash
   PORT=8004 python main.py
   ```

## Configuration

Available environment variables:

- `PORT`: Server port (default: 8004)
- `HOST`: Server host (default: 0.0.0.0)

## Endpoints

- `GET /`: API info
- `GET /api/v1/resources/stats`: Current resource usage (JSON)
- `GET /api/v1/resources/stats/stream`: Real-time stats stream (Server-Sent Events)
- `GET /api/v1/resources/health`: Monitoring health check
