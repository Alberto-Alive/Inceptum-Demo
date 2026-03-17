const express = require("express");
const path = require("path");
const fs = require("fs");

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

// Load .env manually (no dotenv dependency)
try {
  const envPath = path.join(__dirname, ".env");
  const envContent = fs.readFileSync(envPath, "utf-8");
  for (const line of envContent.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const idx = trimmed.indexOf("=");
    if (idx === -1) continue;
    const key = trimmed.slice(0, idx).trim();
    const val = trimmed.slice(idx + 1).trim();
    if (!process.env[key]) process.env[key] = val;
  }
} catch {
  // .env file is optional if env vars are set externally
}

const PROVIDERS = {
  groq: {
    baseUrl: "https://api.groq.com/openai/v1/chat/completions",
    envKey: "GROQ_API_KEY",
  },
  cerebras: {
    baseUrl: "https://api.cerebras.ai/v1/chat/completions",
    envKey: "CEREBRAS_API_KEY",
  },
};

// Returns server-side defaults (from .env)
app.get("/api/defaults", (_req, res) => {
  let provider = "";
  let apiKey = "";
  let model = "";

  if (process.env.GROQ_API_KEY) {
    provider = "groq";
    apiKey = process.env.GROQ_API_KEY;
    model = "llama-3.3-70b-versatile";
  } else if (process.env.CEREBRAS_API_KEY) {
    provider = "cerebras";
    apiKey = process.env.CEREBRAS_API_KEY;
    model = "llama3.1-8b";
  }

  // Mask key for display — send first 8 + last 4 chars
  const masked =
    apiKey.length > 12
      ? apiKey.slice(0, 8) + "..." + apiKey.slice(-4)
      : apiKey
        ? "***"
        : "";

  res.json({ provider, maskedKey: masked, model, hasKey: !!apiKey });
});

// Server-side throttle: enforce minimum gap between outbound LLM calls
// Groq free tier allows ~30 req/min, so 3s minimum gap keeps us safe
const MIN_GAP_MS = 3000;
let lastCallTime = 0;

async function throttle() {
  const now = Date.now();
  const elapsed = now - lastCallTime;
  if (elapsed < MIN_GAP_MS) {
    await new Promise((r) => setTimeout(r, MIN_GAP_MS - elapsed));
  }
  lastCallTime = Date.now();
}

// Unified chat completion proxy
// Accepts client-provided key/provider/model OR falls back to .env defaults
app.post("/api/chat", async (req, res) => {
  const { messages, provider, apiKey, model, max_tokens } = req.body;

  if (!Array.isArray(messages) || messages.length === 0) {
    return res.status(400).json({ error: "messages must be a non-empty array" });
  }

  // Resolve provider config
  let baseUrl, resolvedKey, resolvedModel;

  if (apiKey && provider) {
    // Client-provided credentials
    const p = PROVIDERS[provider];
    if (!p) {
      return res.status(400).json({ error: `Unknown provider: ${provider}` });
    }
    baseUrl = p.baseUrl;
    resolvedKey = apiKey;
    resolvedModel = model || (provider === "groq" ? "llama-3.3-70b-versatile" : "llama3.1-8b");
  } else {
    // Fall back to .env
    if (process.env.GROQ_API_KEY) {
      baseUrl = PROVIDERS.groq.baseUrl;
      resolvedKey = process.env.GROQ_API_KEY;
      resolvedModel = model || "llama-3.3-70b-versatile";
    } else if (process.env.CEREBRAS_API_KEY) {
      baseUrl = PROVIDERS.cerebras.baseUrl;
      resolvedKey = process.env.CEREBRAS_API_KEY;
      resolvedModel = model || "llama3.1-8b";
    } else {
      return res.status(500).json({
        error: "No API key configured. Paste one in the settings bar or set it in .env",
      });
    }
  }

  await throttle();

  const MAX_RETRIES = 3;
  const reqBody = JSON.stringify({
    model: resolvedModel,
    messages,
    temperature: 0.7,
    max_tokens: max_tokens || 256,
  });
  const reqHeaders = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${resolvedKey}`,
  };

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(baseUrl, {
        method: "POST",
        headers: reqHeaders,
        body: reqBody,
      });

      if (response.status === 429) {
        // Rate limited — wait and retry
        const retryAfter = response.headers.get("retry-after");
        const waitMs = retryAfter ? parseFloat(retryAfter) * 1000 : (attempt + 1) * 2000;
        console.log(`Rate limited (429), retrying in ${Math.round(waitMs)}ms (attempt ${attempt + 1}/${MAX_RETRIES})`);
        if (attempt < MAX_RETRIES) {
          await new Promise((r) => setTimeout(r, waitMs));
          continue;
        }
        return res.status(429).json({ error: "Rate limited by provider. Wait a moment and try again." });
      }

      if (!response.ok) {
        const text = await response.text();
        console.error("LLM API error:", response.status, text);
        return res.status(502).json({ error: `LLM API error: ${response.status}` });
      }

      const data = await response.json();
      const reply = data.choices?.[0]?.message?.content;

      if (!reply) {
        return res.status(502).json({ error: "Empty response from LLM" });
      }

      return res.json({ message: reply });
    } catch (err) {
      console.error("Request failed:", err);
      if (attempt < MAX_RETRIES) {
        await new Promise((r) => setTimeout(r, (attempt + 1) * 1000));
        continue;
      }
      return res.status(500).json({ error: "Failed to reach LLM provider" });
    }
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
