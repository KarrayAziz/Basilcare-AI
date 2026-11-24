# Farmer assistant chat

After this PR is merged, build the latest main and launch it yourself:

```bash
bash start.sh --build
```

Keep `GEMINI_API_KEY` in the ignored `deploy/.env`. The launch script adds a dedicated
`ASSISTANT_SERVICE_KEY` if absent. The Compose stack runs a small internal Python service;
its code is mounted from `iot/ai/service`, with no additional pip packages. WildFly's image
must be rebuilt for the new API and frontend. No model weights need downloading.

Open `https://www.basilcare.test/`, sign in, then choose **Assistant**. Try “How should I
prune basil?” The answer shows the original curated note and a source link. No chat box is
added to the Admin website. An Admin can use the Farmer website, as before.

The key stays server-side, in the Python service; the browser only sends its IAM token to
the Java API. Requests follow:

```
Farmer PWA -> Java API (login + role + rate limit)
           -> internal Python assistant (service key + public notes)
           -> Gemini (API key)
           -> answer with approved source links
```

This is public gardening Q&A, not live readings, diagnosis or pump control. There is no
persistent chat history or conversation context sent with the next question. The browser
keeps at most ten exchanges until navigation/reload. Questions must be English, 1–2000
characters. A public-garden answer does not establish a hydroponic target.

If it is unavailable, check your Gemini project quota/key and that both containers have
the same dedicated service key. Don't paste secret values or full Compose config into
issues. Service ports stay internal; no Python port should be published. The complete
technical contract, limits and privacy behavior are in `iot/ai/service/README.md`.

Development verification uses isolated HTTP fixtures, offline provider mocks and hosting
CI browser checks. No production stack or real model service was started by the agent
for this PR. CI does not use your Gemini key. Codex assisted Aziz Karray with the work.
