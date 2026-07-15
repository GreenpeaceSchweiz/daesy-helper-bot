# Purpose

# Local Set Up
Follow these steps to set up your local environment for development.

**Set Up**
1. Clone the repository
2. Run `uv sync`
3. Create a `.env` file based on `.env.example` and complete it with the secrets for your development Slack App, Asana Project, etc.

*Optional: If you like, you can switch to `InMemorySessionService()` and to using the free tier models in Google AI Studio for local development. For the former, adjust the code in `main.py`. For the latter, make sure to set `GEMINI_API_KEY=[your_key]` & `GOOGLE_GENAI_USE_VERTEXAI=FALSE` in `.env`.* 

**Running locally**
4. Start daesy_helper: `python main.py`
5. Start `ngrok`(or similar) using the same port: `ngrok http 8080`.

# Pushing to Cloud Run
**Store Secrets**


**Create Service Account**
```
gcloud iam service-accounts create daesy-helper-bot \
    --description="Service account for the DaESy Helper Bot" \
    --display-name="DaESy Helper Bot"
```

**Grant Permissions**
```
# 1. Allow it to read your scoped secrets
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:daesy-helper-bot@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --condition="expression=resource.name.startsWith('projects/YOUR_PROJECT_ID/secrets/daesy_helper_bot_'),title=Allow Only DaESy Helper Bot Secrets,description=Limits secret access to helper bot prefixed secrets"

# 2. Allow it to call Vertex AI models and the Agent Engine
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:daesy-helper-bot@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# 3. Allow it to write logs to Cloud Logging so you can debug it
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:daesy-helper-bot@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/logging.logWriter"
```

**Build the Artifact in Cloud Buil**
`gcloud builds submit --config=cloudbuild.yaml .`

**Push to Cloud Run**
```
gcloud run deploy daesy-helper-bot-dev `
  --image="europe-west6-docker.pkg.dev/gpch-daesy/cloud-run-source-deploy/daesy-helper-bot-dev:latest" `  --allow-unauthenticated `
  --region europe-west6 `
  --memory 1Gi `
  --no-cpu-throttling `
  --cpu-boost `
  --min-instances=0 `
  --max-instances=1 `
  --service-account="daesy-helper-bot-dev@gpch-daesy.iam.gserviceaccount.com" `
  --set-env-vars=[...]
```

# Security Considerations
Because connection to Slack is handled via Webhooks, the Cloud Run URL needs to be public (option `--allow-unauthenticated`). This is a potential security risk.
Current mitigation measures:
- All incoming requests are handled by Slack Bolt's AsyncApp and verified using the `SLACK_SIGNING_SECRET`.
- (Unlikely) DDOS attacks can cause service interruptions but only limited cost spikes due to `--max-instances=1`.


# Future Improvements
## Introduce Context Caching
Incurs some costs for the cache, but reduces costs for the model execution and reduces latency.
