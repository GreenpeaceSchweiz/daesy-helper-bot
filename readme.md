# Purpose

# Local Set Up
Follow these steps to set up your local environment for development.

**Set Up**
1. Clone the repository
2. Run `uv sync`
3. Create a `.env` file based on `.env.example` and complete it with the secrets for your development Slack App, Asana Project, etc.

*Optional: If you like, you can switch to `InMemorySessionService()` and to using the free tier models in Google AI Studio for local development. For the former, adjust the code in `main.py`. For the latter, make sure to set `GEMINI_API_KEY=[your_key]` & `GOOGLE_GENAI_USE_VERTEXAI=FALSE` in `.env`.* 

**Running locally**
4. Start uvicorn: `uv run uvicorn main:api --reload --port 8080`
5. Start `ngrok`(or similar) using the same port: `ngrok http 8080`.

# Pushing to Cloud Run

```
gcloud run deploy slack-vertex-bot \
  --source . \
  --allow-unauthenticated \
  --region eu \
  --set-env-vars="SLACK_BOT_TOKEN=xoxb-prod-token,SLACK_SIGNING_SECRET=prod-secret"
```