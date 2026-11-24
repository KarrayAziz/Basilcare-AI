# Farmer assistant chat

After this PR is merged, build the latest main and launch it yourself:

```bash
bash start.sh --build
```

Keep `GEMINI_API_KEY` in the ignored `deploy/.env`. The launch script adds a dedicated
`ASSISTANT_SERVICE_KEY` if absent. The Compose stack runs a small internal Python service;
its code is mounted from `iot/ai/service`, with no additional pip packages. WildFly's image
must be rebuilt for the new API and frontend. The script also restarts the Python
assistant so it reloads changed source files. No model weights need downloading.
If you update only the assistant's Python source while the stack is already running, use
`docker compose -f deploy/compose.yaml restart assistant`; rebuilding only WildFly will
not reload Python modules in an existing assistant process.

Open `https://www.basilcare.test/`, sign in, then choose **Assistant**. Try “Comment dois-je
tailler le basilic ?” Gemini receives all five public notes as context and writes an answer
in the question's language, with saved source links. No chat box is
added to the Admin website. An Admin can use the Farmer website, as before.

The key stays server-side, in the Python service; the browser only sends its IAM token to
the Java API. Requests follow:

```
Farmer PWA -> Java API (login + role + rate limit)
           -> internal Python assistant (service key + all public notes)
           -> Gemini (API key)
           -> answer with approved source links
```

This is public gardening Q&A, not live readings, diagnosis or pump control. There is no
persistent chat history or conversation context sent with the next question. The browser
keeps at most ten exchanges until navigation/reload. Questions may be French or English, 1–2000 characters. A public-garden answer does not establish a hydroponic target.

If it is unavailable, check your Gemini project quota/key and that both containers have
the same dedicated service key. Don't paste secret values or full Compose config into
issues. Service ports stay internal; no Python port should be published. The complete
technical contract, limits and privacy behavior are in `iot/ai/service/README.md`.

Development verification uses isolated HTTP fixtures, offline provider mocks and hosting
CI browser checks. No production stack or real model service was started by the agent
for this PR. CI does not use your Gemini key. Codex assisted Aziz Karray with the work.
