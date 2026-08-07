# CraveLV — Phase One MVP

CraveLV is a working browser-based marketing workspace for food-truck businesses.

## Included now

- Dashboard
- Multiple food-truck brands
- Facebook and Instagram caption generator
- Content calendar and post-status workflow
- Catering lead tracker
- Customer-reply workspace
- Optional OpenAI caption generation
- Render deployment configuration

## Not included yet

- Facebook or Instagram account connection
- Automatic publishing
- Automatic comment replies
- User signup, subscriptions, or payments
- Separate accounts for outside food-truck customers

Those are later SaaS phases. This repository is the verified Phase One foundation.

## Deploy on Render

This project contains `render.yaml`. After the files are in a GitHub repository, Render can create the web service from the repository.

Manual settings, if requested:

- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

## Optional AI setup

Add an environment variable in Render:

- Key: `OPENAI_API_KEY`
- Value: your OpenAI API key

Without a key, CraveLV uses its built-in caption generator.

## Data note

The current MVP uses SQLite. On a free cloud service, data may not persist through every redeployment. A production SaaS version should use PostgreSQL before accepting paying customers.
