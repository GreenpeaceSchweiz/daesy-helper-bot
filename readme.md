# Purpose
An AI agent that interacts with users via Slack and helps them with DaESy tasks.

Current functionality:
- Write Asana tickets, either based on 1:1 conversations with the bot or from thread context if tagged in a message thread.

# Architecture
The agent consists of the following elements:
- UI Layers: Slack App (interactive), Asana (output only)
- Orchestrator: Python App (Google ADK, Slack Bolt, Asana), built and hosted in the Google Cloud [cloudbuild.googleapis.com, artifactregistry.googleapis.com, run.googleapis.com]
- LLM: Gemini via Vertex AI API [aiplatform.googleapis.com]
- Session Service: Vertex AI Session Service [aiplatform.googleapis.com]

# Set Up and Deployment
## Development Environment
Follow these steps to set up your local environment for development.

**Set Up**
1. Install and set up *Task* (`winget install Task.Task`) and *Google Cloud CLI*
2. Clone the repository
3. Run `uv sync`
4. Create `.env` file based on `.env.example` and complete it with the secrets for your Slack App, Asana Project, etc.

*Optional: If you like, for development you can switch to `InMemorySessionService()` and to using the free tier models in Google AI Studio for local development. For the former, adjust the code in `main.py`. For the latter, make sure to set `GEMINI_API_KEY=[your_key]` & `GOOGLE_GENAI_USE_VERTEXAI=FALSE` in `.env`.* 

**Running locally**
1. Start daesy_helper: `task dev:local`
2. Start `ngrok` in a separate terminal: `task:dev:tunnel`.

## Slack App
1. Use `daesy_helper_bot\slack\manifest.yaml` to set up your slack app.
2. Update `.env` files with the relevant slack ids.

## Google Cloud
1. Create agent engine using `scripts/create_agent_engine.py` and update `.env` files with the engine id.
2. Enable APIs, Create SAs, and Set Up Permissions: `task setup:all`
3. Compile and deploy: `task ship:all`


More fine-grained tasks are available. See `Taskfile.yml`.

# Security Considerations
Because connection to Slack is handled via Webhooks, the Cloud Run URL needs to be public (option `--allow-unauthenticated`). This is a potential security risk.
Mitigation measures:
- All incoming requests are handled by Slack Bolt's AsyncApp and verified using the `SLACK_SIGNING_SECRET`.
- (Unlikely) DDOS attacks can cause service interruptions but only limited cost spikes due to `--max-instances=1`.
- (Optional) Configure a WAF (i.e. Google Cloud Armor) to only allow through requests from known Slack IPs.
