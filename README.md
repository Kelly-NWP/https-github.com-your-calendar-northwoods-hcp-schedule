# Northwoods Plumbing HCP Schedule Board

Two-month, TV-friendly schedule board for Northwoods Plumbing LLC.

Technician colors:
- Dylan — Blue
- Spencer — Red
- Dawson — Green
- Brian — Black

## Render
Build command: `pip install -r requirements.txt`
Start command: `gunicorn app:app`

Add the Housecall Pro API key in Render as the environment variable `HCP_API_KEY`.
Never commit the API key to GitHub.
