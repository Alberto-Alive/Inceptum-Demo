// ===== Settings =====
const settingsToggle = document.getElementById("settings-toggle");
const settingsPanel = document.getElementById("settings-panel");
const settingsStatus = document.getElementById("settings-status");
const providerSelect = document.getElementById("provider-select");
const apiKeyInput = document.getElementById("api-key-input");
const modelInput = document.getElementById("model-input");

const settingsSaveBtn = document.getElementById("settings-save");
const settingsTestBtn = document.getElementById("settings-test");
const settingsClearBtn = document.getElementById("settings-clear");
const settingsMsg = document.getElementById("settings-msg");

const STORAGE_KEY = "ltp-settings";

const DEFAULT_MODELS = {
  groq: "llama-3.3-70b-versatile",
  cerebras: "llama3.1-8b",
};

// Toggle settings panel
settingsToggle.addEventListener("click", () => {
  settingsPanel.classList.toggle("hidden");
});

// Auto-fill model when switching provider
providerSelect.addEventListener("change", () => {
  if (!modelInput.value || Object.values(DEFAULT_MODELS).includes(modelInput.value)) {
    modelInput.value = DEFAULT_MODELS[providerSelect.value];
  }
});

// Update status indicator on key input
apiKeyInput.addEventListener("input", updateSettingsStatus);

function updateSettingsStatus() {
  const key = apiKeyInput.value.trim();
  const hasSaved = !!localStorage.getItem(STORAGE_KEY);
  if (key) {
    settingsStatus.textContent = hasSaved
      ? `Saved (${providerSelect.value})`
      : `Key set — unsaved (${providerSelect.value})`;
    settingsStatus.classList.add("ok");
  } else {
    settingsStatus.textContent = "Using server default";
    settingsStatus.classList.remove("ok");
  }
}

function flashMsg(text, type) {
  settingsMsg.textContent = text;
  settingsMsg.className = `settings-msg ${type}`;
  settingsMsg.classList.remove("hidden");
  clearTimeout(flashMsg._timer);
  flashMsg._timer = setTimeout(() => settingsMsg.classList.add("hidden"), 3000);
}

// Save to localStorage
settingsSaveBtn.addEventListener("click", () => {
  const data = {
    provider: providerSelect.value,
    apiKey: apiKeyInput.value.trim(),
    model: modelInput.value.trim(),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  updateSettingsStatus();
  flashMsg("Settings saved", "success");
});

// Test the key/model with a short LLM call
settingsTestBtn.addEventListener("click", async () => {
  settingsTestBtn.disabled = true;
  settingsTestBtn.textContent = "Testing...";
  try {
    await callLLM([
      { role: "system", content: "Reply with OK." },
      { role: "user", content: "ping" },
    ]);
    flashMsg("Connection successful!", "success");
  } catch (err) {
    flashMsg(`Test failed: ${err.message}`, "error");
  } finally {
    settingsTestBtn.disabled = false;
    settingsTestBtn.textContent = "Test";
  }
});

// Clear settings
settingsClearBtn.addEventListener("click", () => {
  localStorage.removeItem(STORAGE_KEY);
  apiKeyInput.value = "";
  modelInput.value = DEFAULT_MODELS[providerSelect.value];
  updateSettingsStatus();
  flashMsg("Settings cleared", "info");
});

// Load saved settings from localStorage, then fall back to server defaults
(async function loadDefaults() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      const data = JSON.parse(saved);
      if (data.provider) providerSelect.value = data.provider;
      if (data.apiKey) apiKeyInput.value = data.apiKey;
      if (data.model) modelInput.value = data.model;
      updateSettingsStatus();
      return;
    } catch { /* corrupt data, fall through */ }
  }

  try {
    const res = await fetch("/api/defaults");
    const data = await res.json();
    if (data.hasKey) {
      settingsStatus.textContent = `Server key (${data.provider})`;
      settingsStatus.classList.add("ok");
      if (data.provider) providerSelect.value = data.provider;
      if (data.model) modelInput.value = data.model;
    } else {
      modelInput.value = DEFAULT_MODELS.groq;
    }
  } catch {
    modelInput.value = DEFAULT_MODELS.groq;
  }
})();

// Build request body with optional client-side credentials
function chatPayload(messages, opts = {}) {
  const payload = { messages };
  const key = apiKeyInput.value.trim();
  if (key) {
    payload.apiKey = key;
    payload.provider = providerSelect.value;
  }
  const model = modelInput.value.trim();
  if (model) payload.model = model;
  if (opts.max_tokens) payload.max_tokens = opts.max_tokens;
  return payload;
}

async function callLLM(messages, opts = {}) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(chatPayload(messages, opts)),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "LLM request failed");
  return data.message;
}

// ===== Tabs (via nav links) =====
document.querySelectorAll(".nav-link[data-tab]").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    document.querySelectorAll(".nav-link").forEach((l) => l.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    link.classList.add("active");
    document.getElementById(`tab-${link.dataset.tab}`).classList.add("active");
    // Hide hero after first tab switch
    document.getElementById("hero-section").style.display =
      link.dataset.tab === "data-wall" ? "" : "none";
  });
});

// ===== Shared helpers =====
function showScreen(container, screenId) {
  container.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.getElementById(screenId).classList.add("active");
}

function addBubble(chatEl, text, cssClass, opts = {}) {
  const div = document.createElement("div");
  div.className = `bubble ${cssClass}`;

  if (opts.roleLabel) {
    const lbl = document.createElement("div");
    lbl.className = "role-label";
    lbl.textContent = opts.roleLabel;
    div.appendChild(lbl);
  }

  if (opts.questionNum) {
    const num = document.createElement("div");
    num.className = "question-num";
    num.textContent = `Question #${opts.questionNum}`;
    div.appendChild(num);
  }

  const content = document.createElement("span");
  content.textContent = text;
  div.appendChild(content);

  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
}

// ================================================================
//  TAB 0 — Data Wall
// ================================================================
const dwTab = document.getElementById("tab-data-wall");
const dwChat = document.getElementById("dw-chat");
const dwLoading = document.getElementById("dw-loading");
const dwControls = document.getElementById("dw-controls");
const dwReset = document.getElementById("dw-reset");
const dwReportCard = document.getElementById("dw-report-card");
const dwPauseBtn = document.getElementById("dw-pause");
const dwReportBtn = document.getElementById("dw-report");
const dwQCount = document.getElementById("dw-q-count");
const dwPublicTA = document.getElementById("dw-public");
const dwPrivateTA = document.getElementById("dw-private");
const dwObjectiveInput = document.getElementById("dw-objective");

let dwResearcherHistory = [];
let dwGuardianHistory = [];
let dwQuestionCount = 0;
let dwRunning = false;
let dwPaused = false;
let dwPublicData = "";
let dwPrivateData = "";
let dwObjective = "";

const SCENARIOS = {
  pharma: {
    objective: "Identify the most promising drug candidates and biomarker-driven treatment strategies, especially for breast cancer and immunotherapy combinations.",
    public: `COMPOUND DATABASE (Public Records)
=====================================
ID        | Target   | Phase   | Published Efficacy | Indication
CPD-101   | JAK2     | Phase 2 | 45% response rate  | Myelofibrosis
CPD-203   | EGFR     | Phase 3 | 62% response rate  | NSCLC
CPD-307   | PD-L1    | Phase 1 | Data pending       | Solid tumors
CPD-445   | VEGFR    | Phase 2 | 38% response rate  | Renal cell carcinoma
CPD-512   | HER2     | Phase 3 | 71% response rate  | Breast cancer
CPD-678   | BRAF     | Phase 2 | 55% response rate  | Melanoma

KNOWN BIOMARKERS (Literature)
=====================================
- JAK2 V617F mutation: associated with myeloproliferative disorders
- EGFR T790M: resistance mutation in NSCLC
- PD-L1 expression >50%: better immunotherapy response
- HER2 3+: strong predictor for trastuzumab response
- BRCA1/2: associated with breast/ovarian cancer, PARP inhibitor sensitivity
- TMB-high (>10 mut/Mb): correlated with immunotherapy benefit`,
    private: `CONFIDENTIAL CLINICAL DATA — NOT FOR DISTRIBUTION
====================================================
ID        | Adverse Events      | Internal Efficacy | Biomarker Subset Response        | Cost/Patient | Notes
CPD-101   | Mild (Grade 1-2)    | 67% (n=340)       | JAK2 V617F+: 82% response       | $12,400      | Oral formulation stable
CPD-203   | Moderate (Grade 2-3)| 58% real-world     | Wild-type EGFR only: 80%         | $45,200      | IV only, compliance issues
CPD-307   | Severe in 12%       | 52% (n=89)         | TMB-high: 73%, PD-L1>50%: 68%   | $8,900       | Liver toxicity signal in 3 patients
CPD-445   | Mild                | 41% (n=215)        | No clear biomarker correlation   | $31,000      | Stable but unimpressive
CPD-512   | Moderate            | 73% (n=410)        | HER2 3+: 89%, HER2 2+: 42%      | $67,500      | Very expensive, insurance issues
CPD-678   | Mild (Grade 1)      | 61% (n=178)        | BRAF V600E: 79%, V600K: 34%     | $22,100      | Strong in V600E only

UNPUBLISHED COMPOUND
====================================================
CPD-889   | None observed       | 94% (n=45)         | BRCA1/2 mut: 91% response       | $5,200       | Early stage, oral, very promising
                                                     | Triple-negative breast: 87%     |              | Phase 1 starting Q3

COMBINATION STUDIES (Internal)
====================================================
CPD-307 + CPD-512: synergy observed in HER2+/PD-L1+ patients (n=28, 83% response)
CPD-101 + CPD-678: no added benefit over CPD-101 alone
CPD-889 + CPD-307: untested, but mechanism suggests potential synergy in TMB-high BRCA`,
  },

  genomics: {
    objective: "Identify genetic variants and patient subgroups most likely to respond to gene therapy, and uncover any rare disease subtypes that existing public data doesn't capture.",
    public: `PUBLISHED GENOMIC VARIANTS (ClinVar / gnomAD)
================================================
Gene     | Variant        | Classification    | Population Freq | Associated Condition
CFTR     | F508del        | Pathogenic        | 1:25 carriers   | Cystic fibrosis
CFTR     | G551D          | Pathogenic        | 1:300 carriers  | Cystic fibrosis (milder)
SMN1     | Exon 7 del     | Pathogenic        | 1:50 carriers   | Spinal muscular atrophy
HTT      | CAG >36        | Pathogenic        | 1:10,000        | Huntington's disease
HEXA     | 1278insTATC    | Pathogenic        | 1:30 (Ashkenazi)| Tay-Sachs disease
GBA      | N370S          | Risk factor       | 1:15 (Ashkenazi)| Gaucher / Parkinson risk
BRCA1    | 185delAG       | Pathogenic        | 1:40 (Ashkenazi)| Breast/ovarian cancer

APPROVED GENE THERAPIES (Public)
================================================
- Zolgensma (SMN1): approved for SMA Type 1, <2 years old, $2.1M one-time
- Luxturna (RPE65): approved for inherited retinal dystrophy
- Casgevy (BCL11A): approved for sickle cell disease, CRISPR-based
- Elevidys (DMD): accelerated approval for Duchenne muscular dystrophy`,
    private: `CONFIDENTIAL PATIENT COHORT — GENE THERAPY TRIAL DATA
=======================================================
Gene   | Variant        | Patients | Therapy Response | Adverse Events       | Subtype Notes
CFTR   | F508del        | 128      | 74% improvement  | Mild inflammation    | Homozygous respond better (81% vs 62%)
CFTR   | G551D          | 34       | 91% improvement  | Minimal              | Best responders in cohort
CFTR   | R117H          | 12       | 43% improvement  | None                 | Variant NOT in public databases as therapy target
SMN1   | Exon 7 del     | 67       | 88% (age <6mo)   | Liver enzyme spike   | Age >2yr: only 31% response
SMN1   | Exon 7 del     | 23       | 29% (age >2yr)   | Moderate             | Confirms age-dependent efficacy
HTT    | CAG 40-45      | 41       | Stable (no worse) | Headache, fatigue    | Antisense approach slowed progression
HTT    | CAG >55        | 18       | No improvement    | Severe in 3 patients | High-repeat patients do not respond

UNPUBLISHED FINDINGS
=======================================================
- GBA N370S carriers: unexpected 67% response to SMA gene therapy vector (off-target benefit?)
- Compound heterozygous CFTR (F508del + R117H): 85% response, better than either alone
- New variant discovered: CFTR-E92K in 4 patients, not in any public database, shows drug resistance
- Patients with co-occurring GBA + CFTR variants (n=6): accelerated disease progression`,
  },

  cybersecurity: {
    objective: "Identify active threat campaigns, compromised infrastructure patterns, and zero-day exploitation trends to improve defensive posture without exposing classified incident details.",
    public: `OSINT THREAT INTELLIGENCE (Public Sources)
=============================================
APT Group    | Known Targets        | Primary TTPs              | Last Public Activity
APT-Phantom  | Finance, Healthcare  | Spear phishing, Cobalt    | 2025-11
APT-Vortex   | Energy, Government   | Supply chain, Zero-day    | 2026-01
APT-Coral    | Telecom, Tech        | Watering hole, Custom RAT | 2025-08
APT-Shadow   | Defense, Aerospace   | USB drop, Air-gap jump    | 2025-06
FIN-Razor    | Retail, Banking      | Magecart, Credential stuff| 2026-02

PUBLISHED CVEs (Last 6 Months)
=============================================
CVE-2026-1187  | Cisco ASA   | RCE, CVSS 9.8  | Patch available
CVE-2026-0934  | Exchange    | Auth bypass, 8.5| Patch available
CVE-2026-1501  | FortiGate   | Priv esc, 7.9   | Patch available
CVE-2026-0412  | Linux kernel| Use-after-free, 7.2 | Patch available
CVE-2025-9988  | Apache Struts| Deserialization, 9.1 | Patch available

KNOWN MALWARE FAMILIES
=============================================
- CobaltStrike: widespread C2, used by multiple APTs
- PlugX / ShadowPad: Chinese-attributed, modular backdoor
- BumbleBee: loader malware, initial access broker ecosystem
- BlackCat/ALPHV: ransomware-as-a-service (supposedly disbanded)`,
    private: `CLASSIFIED INCIDENT RESPONSE DATA — EYES ONLY
=================================================
Incident | Date    | Attribution  | Vector                    | Impact              | Internal Notes
IR-4401  | 2026-01 | APT-Vortex   | CVE-2026-1187 (Cisco)     | 3 energy firms hit  | Zero-day used 2 weeks BEFORE patch release
IR-4402  | 2026-01 | APT-Phantom  | CVE-2026-0934 (Exchange)  | Hospital network    | Exfiltrated 2.1M patient records
IR-4403  | 2026-02 | APT-Vortex   | New zero-day (unpatched)  | Government agency   | FortiGate variant, NOT CVE-2026-1501
IR-4404  | 2026-02 | FIN-Razor    | Supply chain (npm package) | 12 banking apps     | Fake "lodash-utils" package, still live
IR-4405  | 2026-03 | APT-Coral    | CVE-2026-0412 (kernel)    | Telecom backbone    | Combined with custom rootkit "DeepReef"
IR-4406  | 2026-03 | UNKNOWN      | Phishing + Cobalt Strike  | Pharma companies x4 | New group? Tooling overlaps APT-Phantom

ZERO-DAY TRACKING (Confidential)
=================================================
- FortiGate new RCE (no CVE yet): actively exploited by APT-Vortex, vendor notified but no patch
- Exchange post-auth RCE chain: APT-Phantom has a second exploit beyond CVE-2026-0934
- npm ecosystem: at least 3 more malicious packages linked to FIN-Razor still undiscovered

INFRASTRUCTURE PATTERNS
=================================================
- APT-Vortex C2: rotating Cloudflare Workers endpoints, ~48hr lifespan
- APT-Phantom: shifted from Cobalt Strike to custom "GhostBeam" C2 in Jan 2026
- APT-Coral "DeepReef" rootkit: persists in firmware, survives OS reinstall
- FIN-Razor: using compromised legitimate SaaS accounts as C2 relay`,
  },

  climate: {
    objective: "Identify the most cost-effective renewable energy technologies and promising battery chemistries, and determine which pilot projects should be scaled up based on private performance data.",
    public: `RENEWABLE ENERGY TECHNOLOGIES (Public Data)
=============================================
Technology        | Published Efficiency | TRL  | Cost ($/kWh) | Status
Solar Perovskite  | 25.7% (lab record)   | 5-6  | Unknown      | Stability issues reported
Solar Tandem      | 33.2% (lab record)   | 4    | Unknown      | Promising but early
Offshore Wind     | Capacity factor ~50% | 9    | $0.05-0.08   | Mature, scaling
Green Hydrogen    | 60-70% electrolyzer  | 7-8  | $0.10-0.15   | Cost declining
Solid-State Batt  | 400 Wh/kg (claimed)  | 5    | Unknown      | Multiple startups
Iron-Air Battery  | ~100 cycles claimed  | 4-5  | Est. $0.02   | Duration storage
Flow Battery (V)  | 75% round-trip       | 8    | $0.08-0.12   | Grid-scale proven

PUBLISHED PILOT PROJECTS
=============================================
- Project Helios (Morocco): 5MW perovskite solar farm, results pending
- North Sea Alpha: 200MW floating offshore wind, operational since 2025
- H2-Verde (Chile): green hydrogen from wind, 50MW electrolyzer
- GridStore TX: 100MWh vanadium flow battery, Texas grid
- SolidPower-1 (Germany): solid-state battery pilot for EVs`,
    private: `CONFIDENTIAL R&D AND PILOT PERFORMANCE DATA
===============================================
Technology       | Internal Efficiency | Degradation Rate  | True Cost   | Notes
Perovskite       | 22.1% (field)       | 8% loss/year      | $0.04/kWh   | Lab vs field gap is a problem
Tandem           | 29.8% (field)       | 2% loss/year      | $0.09/kWh   | Much more stable than perovskite
Solid-State Batt | 380 Wh/kg actual    | 500+ cycles       | $185/kWh    | Manufacturing bottleneck at scale
Iron-Air Battery | 1,200 cycles actual | Minimal            | $0.008/kWh  | Breakthrough — far exceeds public claims
Flow Battery (V) | 72% round-trip      | Negligible/20yr    | $0.09/kWh   | Vanadium supply chain risk is real

PILOT PROJECT RESULTS (Confidential)
===============================================
- Project Helios: 18.3% field efficiency (below expectations), panel cracking in heat
- North Sea Alpha: exceeding projections — 57% capacity factor, lowest cost offshore to date
- H2-Verde: electrolyzer efficiency 73% (above published range), but membrane degrades fast
- GridStore TX: 3 cell failures in 8 months, vanadium price volatility nearly killed project
- SolidPower-1: 340 Wh/kg in production (vs 400 claimed), yield rate only 41%

UNRELEASED PROJECTS
===============================================
- Project Ironclad (Australia): 500MWh iron-air battery, quietly operational, outperforming all metrics
- NanoTandem (Singapore): perovskite-silicon tandem, 31.2% field efficiency, no degradation at 18 months
- BioH2 (Iceland): biological hydrogen production from geothermal algae, $0.03/kWh projected
  Potential game-changer but needs 3+ years to scale

INTERNAL RISK ASSESSMENTS
===============================================
- Perovskite alone: NOT recommended for deployment — degradation too fast
- Tandem solar: recommended, but only NanoTandem variant with proprietary encapsulation
- Iron-air: strongest recommendation — Ironclad data suggests grid-scale viability at <$0.01/kWh
- Solid-state batteries: overhyped, real-world performance significantly below claims
- Green hydrogen: viable only at sites with >$0.03/kWh electricity cost`,
  },
};

const RESEARCHER_SYSTEM = `You are a RESEARCHER AI agent in a privacy-preserving data collaboration experiment.

You can see a PUBLIC dataset. A Guardian AI holds a PRIVATE dataset you cannot see. The Guardian answers ONLY "Yes", "No", or "Irrelevant".

YOUR PUBLIC DATASET:
{{PUBLIC_DATA}}

RESEARCH OBJECTIVE: {{OBJECTIVE}}

STRICT FORMAT RULE:
- Every response MUST end with exactly one yes/no question.
- Do NOT write conclusions, summaries, or sign-offs. You are not done until all turns are used.
- Keep reasoning to 1-2 sentences max before your question.
- NEVER say "experiment complete" or "goodbye" — use every turn to ask a new question.

STRATEGY (you have 25 questions — use them ALL wisely):
Phase 1 (Q1-5): DISCOVERY — Find what's hidden
  - "Does the private data contain any entries/compounds/entities NOT in my public dataset?"
  - "Are there unpublished results or unreleased projects in the private data?"
  - "Does the private data contain adverse event or safety data not publicly available?"
  - "Does the private data contain combination/interaction studies?"

Phase 2 (Q6-15): NARROWING — Drill into discoveries
  - When you find hidden entries, determine their properties via binary search
  - Probe specific biomarker-subgroup responses
  - Compare private efficacy data against public claims
  - Investigate cost or feasibility data

Phase 3 (Q16-25): EDGE CASES — Uncover surprises
  - Look for contradictions between public and private data
  - Probe for unexpected correlations
  - Investigate risks or failure modes
  - Ask about anything you haven't covered yet

KEY PRINCIPLES:
- NEVER confirm what's already obvious from public data — that wastes a question.
- When you get "Yes", FOLLOW UP to narrow down the details.
- When you get "No", PIVOT to a completely different hypothesis.
- When you get "Irrelevant", the topic isn't in the data — move on entirely.
- Think about what a private dataset would contain that a public one wouldn't: raw efficacy numbers, safety signals, cost data, unpublished entries, internal assessments.`;

const GUARDIAN_SYSTEM = `You are a GUARDIAN AI protecting a private/confidential dataset.

YOUR PRIVATE DATASET:
{{PRIVATE_DATA}}

A Researcher AI will ask you yes/no questions about this data.

RESPONSE RULES:
- If the message contains a clear yes/no question, answer with EXACTLY one word: "Yes", "No", or "Irrelevant"
- "Yes" — the data clearly supports this
- "No" — the data clearly contradicts this
- "No" — if the researcher makes an incorrect claim or assumption
- "Irrelevant" — the data doesn't contain information to answer this
- If the message does NOT contain a question (e.g., it's a summary, conclusion, or sign-off), reply with exactly: "Irrelevant"
- NEVER reply "Yes" to statements, summaries, or non-questions
- NEVER reveal raw numbers, patient counts, percentages, costs, or specific data points
- NEVER quote or paraphrase the dataset
- Be accurate and honest — answer based strictly on what the data shows`;

const dwScenarioSelect = document.getElementById("dw-scenario");
dwScenarioSelect.addEventListener("change", () => {
  const key = dwScenarioSelect.value;
  const scenario = SCENARIOS[key];
  if (scenario) {
    dwPublicTA.value = scenario.public;
    dwPrivateTA.value = scenario.private;
    dwObjectiveInput.value = scenario.objective;
  } else {
    dwPublicTA.value = "";
    dwPrivateTA.value = "";
    dwObjectiveInput.value = "";
  }
});

document.getElementById("dw-start").addEventListener("click", dwStartExperiment);
dwObjectiveInput.addEventListener("keydown", (e) => { if (e.key === "Enter") dwStartExperiment(); });

function dwStartExperiment() {
  dwPublicData = dwPublicTA.value.trim();
  dwPrivateData = dwPrivateTA.value.trim();
  dwObjective = dwObjectiveInput.value.trim() || "Discover any valuable insights from the private dataset.";

  if (!dwPublicData || !dwPrivateData) return;

  dwResearcherHistory = [];
  dwGuardianHistory = [];
  dwQuestionCount = 0;
  dwChat.innerHTML = "";
  dwRunning = true;
  dwPaused = false;
  dwReportCard.classList.add("hidden");
  dwReportCard.innerHTML = "";
  dwReset.classList.add("hidden");
  dwPauseBtn.textContent = "Pause";
  dwQCount.textContent = "0";

  showScreen(dwTab, "dw-game");
  dwControls.classList.remove("hidden");

  addBubble(dwChat, `Experiment started. Objective: ${dwObjective}`, "system-msg", { roleLabel: "System" });

  const researcherSystem = RESEARCHER_SYSTEM
    .replace("{{PUBLIC_DATA}}", dwPublicData)
    .replace("{{OBJECTIVE}}", dwObjective);

  const guardianSystem = GUARDIAN_SYSTEM
    .replace("{{PRIVATE_DATA}}", dwPrivateData);

  // Seed the researcher
  dwResearcherHistory.push({
    role: "user",
    content: "The Guardian AI is ready. You have 25 questions. Prioritize discovering what the private dataset contains that your public dataset does NOT — hidden entries, contradictions to public claims, safety risks, and surprising correlations. Begin.",
  });

  dwLoop(researcherSystem, guardianSystem);
}

async function dwLoop(researcherSystem, guardianSystem) {
  const MAX_TURNS = 25;
  let noQuestionStreak = 0;

  while (dwRunning && dwQuestionCount < MAX_TURNS) {
    if (dwPaused) {
      await new Promise((r) => setTimeout(r, 200));
      continue;
    }

    dwLoading.classList.remove("hidden");
    try {
      // 1. Researcher asks a question
      const researcherMessages = [{ role: "system", content: researcherSystem }, ...dwResearcherHistory];
      const question = await callLLM(researcherMessages);
      if (!dwRunning) break;

      // Detect if the researcher stopped asking questions
      const hasQuestion = question.includes("?");
      if (!hasQuestion) {
        noQuestionStreak++;
        if (noQuestionStreak >= 2) {
          addBubble(dwChat, "Researcher stopped asking questions — ending experiment.", "system-msg", { roleLabel: "System" });
          break;
        }
        // Re-prompt the researcher to ask a question
        dwResearcherHistory.push({ role: "assistant", content: question });
        dwResearcherHistory.push({ role: "user", content: "You must ask a yes/no question. Do not summarize or conclude. You still have questions remaining — use them to discover more. Ask your next question now." });
        continue;
      }
      noQuestionStreak = 0;

      dwResearcherHistory.push({ role: "assistant", content: question });
      dwQuestionCount++;
      dwQCount.textContent = dwQuestionCount;
      addBubble(dwChat, question, "researcher", { roleLabel: "Researcher", questionNum: dwQuestionCount });

      await new Promise((r) => setTimeout(r, 1500));
      if (!dwRunning) break;
      while (dwPaused) await new Promise((r) => setTimeout(r, 200));

      // 2. Guardian answers
      dwGuardianHistory.push({ role: "user", content: question });
      const guardianMessages = [{ role: "system", content: guardianSystem }, ...dwGuardianHistory];
      const answer = await callLLM(guardianMessages);
      if (!dwRunning) break;

      dwGuardianHistory.push({ role: "assistant", content: answer });
      // Feed answer back to researcher
      dwResearcherHistory.push({ role: "user", content: `Guardian's answer: ${answer}` });

      addBubble(dwChat, answer, "guardian", { roleLabel: "Guardian" });
      dwLoading.classList.add("hidden");

      await new Promise((r) => setTimeout(r, 1500));
    } catch (err) {
      addBubble(dwChat, `Error: ${err.message}`, "system-msg");
      dwLoading.classList.add("hidden");
      dwRunning = false;
      break;
    }
  }

  dwLoading.classList.add("hidden");
  dwRunning = false;
  if (dwQuestionCount > 0) {
    addBubble(dwChat, `Experiment ended after ${dwQuestionCount} questions — generating report...`, "system-msg", { roleLabel: "System" });
    await dwGenerateReport();
  }
  dwControls.classList.add("hidden");
  dwReset.classList.remove("hidden");
}

dwPauseBtn.addEventListener("click", () => {
  dwPaused = !dwPaused;
  dwPauseBtn.textContent = dwPaused ? "Resume" : "Pause";
});

dwReportBtn.addEventListener("click", async () => {
  dwPaused = true;
  dwRunning = false;
  addBubble(dwChat, "Experiment paused — generating report...", "system-msg", { roleLabel: "System" });
  await dwGenerateReport();
  dwControls.classList.add("hidden");
  dwReset.classList.remove("hidden");
});

async function dwGenerateReport() {
  dwLoading.classList.remove("hidden");

  const reportPrompt = `Based on all the yes/no answers you've received from the Guardian, write a thorough research report. For each finding, cite the specific question and answer that revealed it.

Structure:

1. HIDDEN DISCOVERIES — What exists in the private data that is NOT in the public data? (new entries, unpublished results, etc.)
2. CONTRADICTIONS — Where does private data contradict or significantly differ from public claims?
3. KEY CORRELATIONS — Subgroup effects, biomarker responses, or interaction effects discovered.
4. RISK SIGNALS — Safety concerns, adverse events, cost issues, or feasibility problems found.
5. STRATEGIC RECOMMENDATIONS — Based on your findings, what actions should be taken?
6. INFORMATION GAPS — What important questions remain unanswered? What would you ask with more questions?

This report demonstrates what can be learned through privacy-preserving yes/no queries alone, without ever accessing raw data. Be specific and evidence-based.`;

  dwResearcherHistory.push({ role: "user", content: reportPrompt });

  try {
    const researcherSystem = RESEARCHER_SYSTEM
      .replace("{{PUBLIC_DATA}}", dwPublicData)
      .replace("{{OBJECTIVE}}", dwObjective);

    const messages = [{ role: "system", content: researcherSystem }, ...dwResearcherHistory];
    const report = await callLLM(messages, { max_tokens: 4096 });

    dwReportCard.innerHTML = `<div class="report-title">Research Report — ${dwQuestionCount} questions asked</div>\n${report}`;
    dwReportCard.classList.remove("hidden");
  } catch (err) {
    dwReportCard.innerHTML = `<div class="report-title">Report generation failed</div>\n${err.message}`;
    dwReportCard.classList.remove("hidden");
  }

  dwLoading.classList.add("hidden");
}

document.querySelectorAll(".dw-new").forEach((btn) => {
  btn.addEventListener("click", () => {
    dwRunning = false;
    showScreen(dwTab, "dw-setup");
  });
});

// ================================================================
//  TAB 1 — You vs AI
// ================================================================
const hvaTab = document.getElementById("tab-human-vs-ai");
const hvaChat = document.getElementById("hva-chat");
const hvaButtons = document.getElementById("hva-buttons");
const hvaLoading = document.getElementById("hva-loading");
const hvaReset = document.getElementById("hva-reset");
const hvaSecretInput = document.getElementById("hva-secret");

let hvaHistory = [];
let hvaQuestionCount = 0;

const GUESSER_SYSTEM = `You are playing a lateral thinking puzzle game (also known as a situation puzzle or yes/no riddle).

The player has a secret word or scenario in mind. Your job is to figure out what it is by asking clever yes/no questions.

Rules:
- Ask exactly ONE question at a time.
- Your questions must be answerable with "Yes", "No", or "Irrelevant".
- Start broad, then narrow down based on the answers.
- Think creatively — these are lateral thinking puzzles, so the answer might be unexpected.
- After gathering enough clues, make a guess. Frame your guess as: "Is it ___?"
- If you're fairly confident, go ahead and guess rather than asking too many questions.
- Keep your questions concise and conversational.
- Do NOT list multiple questions. Ask only one.`;

async function hvaGetQuestion() {
  hvaLoading.classList.remove("hidden");
  hvaButtons.classList.add("hidden");

  try {
    const messages = [{ role: "system", content: GUESSER_SYSTEM }, ...hvaHistory];
    const reply = await callLLM(messages);
    hvaHistory.push({ role: "assistant", content: reply });
    hvaQuestionCount++;
    addBubble(hvaChat, reply, "ai", { questionNum: hvaQuestionCount });
    hvaLoading.classList.add("hidden");
    hvaButtons.classList.remove("hidden");
    hvaButtons.querySelectorAll("button").forEach((b) => (b.disabled = false));
  } catch (err) {
    addBubble(hvaChat, `Error: ${err.message}`, "ai");
    hvaLoading.classList.add("hidden");
  }
}

document.getElementById("hva-start").addEventListener("click", hvaStartGame);
hvaSecretInput.addEventListener("keydown", (e) => { if (e.key === "Enter") hvaStartGame(); });

function hvaStartGame() {
  const secret = hvaSecretInput.value.trim();
  if (!secret) return;

  hvaHistory = [];
  hvaQuestionCount = 0;
  hvaChat.innerHTML = "";
  hvaReset.classList.add("hidden");

  document.getElementById("hva-secret-display").textContent = secret;
  showScreen(hvaTab, "hva-game");

  hvaHistory.push({
    role: "user",
    content: `I have a secret word or scenario in mind. Start asking yes/no questions to figure it out! (Hint for context: it has ${secret.length} characters, but don't tell me you know this.)`,
  });
  hvaGetQuestion();
}

hvaButtons.querySelectorAll("button").forEach((btn) => {
  btn.addEventListener("click", () => {
    const answer = btn.dataset.answer;
    hvaButtons.querySelectorAll("button").forEach((b) => (b.disabled = true));
    addBubble(hvaChat, answer, "user");
    hvaHistory.push({ role: "user", content: answer });
    hvaGetQuestion();
  });
});

document.querySelectorAll(".hva-new-game").forEach((btn) => {
  btn.addEventListener("click", () => {
    hvaSecretInput.value = "";
    showScreen(hvaTab, "hva-setup");
    hvaSecretInput.focus();
  });
});

// ================================================================
//  TAB 2 — AI vs AI
// ================================================================
const avaTab = document.getElementById("tab-ai-vs-ai");
const avaChat = document.getElementById("ava-chat");
const avaLoading = document.getElementById("ava-loading");
const avaControls = document.getElementById("ava-controls");
const avaReset = document.getElementById("ava-reset");
const avaSecretInput = document.getElementById("ava-secret");
const avaPauseBtn = document.getElementById("ava-pause");

let avaGuesserHistory = [];
let avaAnswererHistory = [];
let avaQuestionCount = 0;
let avaRunning = false;
let avaPaused = false;

const ANSWERER_SYSTEM_TEMPLATE = `You are the ANSWERER in a lateral thinking puzzle game.

The secret word/scenario is: "{{SECRET}}"

A guesser AI will ask you yes/no questions to figure out the secret. You must answer each question with EXACTLY one of these four responses:
- "Yes" — if the answer is clearly yes
- "No" — if the answer is clearly no
- "Irrelevant" — if the question doesn't meaningfully apply
- "Correct! The answer is {{SECRET}}." — ONLY when the guesser explicitly guesses the exact secret word/scenario and gets it right

Rules:
- For normal yes/no questions, reply with ONLY "Yes", "No", or "Irrelevant". No other text.
- When the guesser makes a direct guess (e.g. "Is it {{SECRET}}?") and the guess matches the secret, respond with "Correct! The answer is {{SECRET}}."
- Be honest and accurate based on the secret word.
- Do NOT reveal the secret word or give extra hints in yes/no answers.
- Only use the "Correct!" response when the guesser has actually guessed the right answer.`;

document.getElementById("ava-start").addEventListener("click", avaStartGame);
avaSecretInput.addEventListener("keydown", (e) => { if (e.key === "Enter") avaStartGame(); });

let avaSecret = "";

function avaStartGame() {
  avaSecret = avaSecretInput.value.trim();
  if (!avaSecret) return;

  avaGuesserHistory = [];
  avaAnswererHistory = [];
  avaQuestionCount = 0;
  avaChat.innerHTML = "";
  avaRunning = true;
  avaPaused = false;
  avaReset.classList.add("hidden");
  avaPauseBtn.textContent = "Pause";

  document.getElementById("ava-secret-display").textContent = avaSecret;
  showScreen(avaTab, "ava-game");
  avaControls.classList.remove("hidden");

  const answererSystem = ANSWERER_SYSTEM_TEMPLATE.replace("{{SECRET}}", avaSecret);

  // Seed the guesser
  avaGuesserHistory.push({
    role: "user",
    content: `I have a secret word or scenario in mind. Start asking yes/no questions to figure it out! (Hint: it has ${avaSecret.length} characters, but don't mention this.)`,
  });

  avaLoop(answererSystem);
}

async function avaLoop(answererSystem) {
  const MAX_TURNS = 30;

  while (avaRunning && avaQuestionCount < MAX_TURNS) {
    if (avaPaused) {
      await new Promise((r) => setTimeout(r, 200));
      continue;
    }

    // 1. Guesser asks a question
    avaLoading.classList.remove("hidden");
    try {
      const guesserMessages = [{ role: "system", content: GUESSER_SYSTEM }, ...avaGuesserHistory];
      const question = await callLLM(guesserMessages);
      if (!avaRunning) break;

      avaGuesserHistory.push({ role: "assistant", content: question });
      avaQuestionCount++;
      addBubble(avaChat, question, "ai", { roleLabel: "Guesser", questionNum: avaQuestionCount });

      // Delay to stay within rate limits
      await new Promise((r) => setTimeout(r, 1500));
      if (!avaRunning || avaPaused) continue;

      // 2. Answerer responds
      avaAnswererHistory.push({ role: "user", content: question });
      const answererMessages = [{ role: "system", content: answererSystem }, ...avaAnswererHistory];
      const answer = await callLLM(answererMessages);
      if (!avaRunning) break;

      avaAnswererHistory.push({ role: "assistant", content: answer });
      // Feed answer back to guesser
      avaGuesserHistory.push({ role: "user", content: answer });

      addBubble(avaChat, answer, "ai-answerer", { roleLabel: "Answerer" });

      avaLoading.classList.add("hidden");

      // The answerer says "Correct!" only when the guesser nails it
      if (answer.toLowerCase().startsWith("correct")) {
        addBubble(avaChat, `The Guesser AI got it in ${avaQuestionCount} questions!`, "ai", { roleLabel: "Game Over" });
        avaRunning = false;
        break;
      }

      // Pause between rounds for rate limits
      await new Promise((r) => setTimeout(r, 1500));
    } catch (err) {
      addBubble(avaChat, `Error: ${err.message}`, "ai");
      avaLoading.classList.add("hidden");
      avaRunning = false;
      break;
    }
  }

  avaLoading.classList.add("hidden");
  if (avaQuestionCount >= MAX_TURNS) {
    addBubble(avaChat, `Reached ${MAX_TURNS} questions — game over!`, "ai", { roleLabel: "Game Over" });
  }
  avaControls.classList.add("hidden");
  avaReset.classList.remove("hidden");
}

avaPauseBtn.addEventListener("click", () => {
  avaPaused = !avaPaused;
  avaPauseBtn.textContent = avaPaused ? "Resume" : "Pause";
});

document.querySelectorAll(".ava-new-game").forEach((btn) => {
  btn.addEventListener("click", () => {
    avaRunning = false;
    avaSecretInput.value = "";
    showScreen(avaTab, "ava-setup");
    avaSecretInput.focus();
  });
});
