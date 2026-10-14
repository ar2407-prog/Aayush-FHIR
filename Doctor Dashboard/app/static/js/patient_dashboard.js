/**
 * static/js/patient_dashboard.js
 *
 * Doctor dashboard: AI chat interface, prescription JSON generation/download,
 * and chat message auto-scrolling.
 */
document.addEventListener("DOMContentLoaded", () => {
  initAIChat();
  initJSONHandling();
  initIntakeSearch();
});

// ============================================================
// 1. AI Chat Interface
// ============================================================
function initAIChat() {
  const form = document.getElementById("ai-chat-form");
  const input = document.getElementById("chat-input");
  const messagesDiv = document.getElementById("chat-messages");
  if (!form || !messagesDiv) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const message = input.value.trim();
    if (!message) return;

    const intakeId = form.querySelector('input[name="intake_id"]').value;

    // Clear input and add optimistic user message
    input.value = "";
    appendMessage(message, "user");
    scrollToBottom();

    // Show thinking indicator
    const thinkingEl = document.createElement("div");
    thinkingEl.className = "flex justify-start";
    thinkingEl.innerHTML = `
      <div class="max-w-xs lg:max-w-md px-4 py-2.5 rounded-xl text-sm bg-white border border-emerald-900/15">
        <div class="flex items-center gap-2">
          <div class="w-2 h-2 rounded-full bg-slate-400 animate-pulse"></div>
          <div class="w-2 h-2 rounded-full bg-slate-400 animate-pulse" style="animation-delay: 0.2s"></div>
          <div class="w-2 h-2 rounded-full bg-slate-400 animate-pulse" style="animation-delay: 0.4s"></div>
        </div>
      </div>
    `;
    messagesDiv.appendChild(thinkingEl);
    scrollToBottom();

    try {
      const response = await fetch("/patient-dashboard/ai-chat", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          intake_id: intakeId,
          user_message: message,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        thinkingEl.remove();
        appendMessage(
          error.error || "An error occurred. Please try again.",
          "assistant"
        );
        scrollToBottom();
        return;
      }

      const data = await response.json();
      thinkingEl.remove();

      // Add AI response
      appendMessage(data.ai_response, "assistant");
      scrollToBottom();

      // If emergency detected, show a banner
      if (data.is_emergency) {
        showEmergencyBanner();
      }

      // If prescription was auto-generated, update the JSON section
      if (data.prescription_json) {
        updateJSONView(data.prescription_json);
      }
    } catch (err) {
      console.error("Chat error:", err);
      thinkingEl.remove();
      appendMessage(
        "Failed to connect to the AI doctor. Please try again.",
        "assistant"
      );
      scrollToBottom();
    }
  });
}

function appendMessage(text, role) {
  const messagesDiv = document.getElementById("chat-messages");
  const msgEl = document.createElement("div");
  msgEl.className = `flex ${role === "user" ? "justify-end" : "justify-start"}`;
  msgEl.innerHTML = `
    <div class="max-w-xs lg:max-w-md px-4 py-2.5 rounded-xl text-sm
      ${
        role === "user"
          ? "bg-emerald-700 text-white"
          : "bg-white border border-emerald-900/15 text-slate-800"
      }">
      ${text}
    </div>
  `;
  messagesDiv.appendChild(msgEl);
}

function scrollToBottom() {
  const messagesDiv = document.getElementById("chat-messages");
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function showEmergencyBanner() {
  const existing = document.querySelector(".emergency-banner");
  if (existing) return;

  const banner = document.createElement("div");
  banner.className =
    "emergency-banner sticky top-0 z-10 bg-red-600 text-white px-6 py-4 rounded-lg flex items-start gap-3 mb-4 animate-pulse";
  banner.innerHTML = `
    <svg class="w-5 h-5 mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
      <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
    </svg>
    <div>
      <p class="font-bold">EMERGENCY DETECTED</p>
      <p class="text-sm">This patient requires immediate medical attention. Alert senior staff immediately.</p>
    </div>
  `;

  document.getElementById("chat-messages").insertAdjacentElement("beforebegin", banner);
}

// ============================================================
// 2. JSON Prescription Handling
// ============================================================
function initJSONHandling() {
  const generateBtn = document.getElementById("generate-rx-btn");
  const copyBtn = document.getElementById("copy-json-btn");
  const downloadBtn = document.getElementById("download-json-btn");

  if (generateBtn) {
    generateBtn.addEventListener("click", generatePrescription);
  }

  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      const output = document.getElementById("json-output");
      if (!output) return;
      navigator.clipboard.writeText(output.textContent);
      copyBtn.innerHTML = `<i data-lucide="check" class="w-3 h-3 inline mr-1"></i>Copied!`;
      setTimeout(() => {
        copyBtn.innerHTML = `<i data-lucide="copy" class="w-3 h-3 inline mr-1"></i>Copy JSON`;
        if (window.lucide) lucide.createIcons();
      }, 2000);
    });
  }

  if (downloadBtn) {
    downloadBtn.addEventListener("click", () => {
      const output = document.getElementById("json-output");
      if (!output) return;

      const blob = new Blob([output.textContent], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `prescription_${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }
}

async function generatePrescription() {
  const intakeId = new URLSearchParams(window.location.search).get("intake_id") ||
    document.querySelector('input[name="intake_id"]')?.value;

  if (!intakeId) {
    alert("Could not find intake ID.");
    return;
  }

  const btn = document.getElementById("generate-rx-btn");
  btn.disabled = true;
  btn.innerHTML = `<span>Generating...</span>`;

  try {
    const response = await fetch(`/patient-dashboard/generate-prescription/${intakeId}`, {
      method: "POST",
    });

    if (!response.ok) {
      const error = await response.json();
      alert("Error: " + (error.error || "Could not generate prescription"));
      return;
    }

    const data = await response.json();
    updateJSONView(data.prescription);

    // Scroll to JSON view
    document.getElementById("json-view").scrollIntoView({ behavior: "smooth" });

    btn.innerHTML = `<i data-lucide="check" class="w-5 h-5"></i><span>Prescription Generated!</span>`;
  } catch (err) {
    console.error("Generation error:", err);
    alert("Failed to generate prescription. Please try again.");
  } finally {
    btn.disabled = false;
    if (window.lucide) lucide.createIcons();
  }
}

function updateJSONView(prescription) {
  const output = document.getElementById("json-output");
  if (output) {
    output.textContent = JSON.stringify(prescription, null, 2);
  }
}

// ============================================================
// 3. Bilingual Intake Search & Filter (English & Ayurvedic Terms)
// ============================================================
const SYMPTOM_SYNONYMS = {
  fever: ["jwara", "jwar", "pyrexia", "bukhar", "taap", "temperature", "santapa", "shita jwara"],
  cough: ["kasa", "kaas", "khasi", "coughing", "shushka kasa", "dry cough", "productive cough"],
  cold: ["pratishyaya", "pratishyay", "sardi", "zukham", "rhinitis", "coryza", "runny nose"],
  headache: ["shirashoola", "shirahshoola", "sir dard", "sirdard", "migraine", "ardhavabhedaka", "head pain"],
  "joint pain": ["sandhivata", "sandhishoola", "sandhi shoola", "arthritis", "osteoarthritis", "jodo ka dard", "joint stiffness", "stiffness"],
  arthritis: ["sandhivata", "amavata", "sandhishoola", "gathiya", "joint pain"],
  "rheumatoid arthritis": ["amavata", "ama vata", "gathiya"],
  acidity: ["amlapitta", "amla pitta", "hyperacidity", "acid reflux", "heartburn", "gerd", "gastritis", "pitta"],
  hyperacidity: ["amlapitta", "amla pitta", "acid reflux", "heartburn", "acidity"],
  heartburn: ["amlapitta", "hrid daha", "khatta pitta", "acidity"],
  "acid reflux": ["amlapitta", "uradhwaga amlapitta", "reflux", "gerd", "acidity"],
  indigestion: ["mandagni", "agnimandya", "ajirna", "ajirnam", "badhazmi", "weak digestion", "dyspepsia"],
  "weak digestion": ["mandagni", "agnimandya", "slow digestion", "reduced digestive power", "indigestion"],
  "loss of appetite": ["aruchi", "agnimandya", "bhukh na lagna", "anorexia", "appetite loss"],
  asthma: ["tamaka shwasa", "shwasa", "swas", "dama", "bronchial asthma"],
  breathlessness: ["shwasa", "shwas", "dyspnea", "shortness of breath", "saans phulna", "difficulty breathing"],
  "shortness of breath": ["shwasa", "dyspnea", "breathlessness", "saans phulna"],
  "chest pain": ["hridshoola", "hrid shoola", "hridroga", "sineme dard", "angina"],
  "stomach pain": ["udarashoola", "udara shoola", "shoola", "pet dard", "abdominal pain", "belly pain", "cramp"],
  "abdominal pain": ["udarashoola", "udara shoola", "pet dard", "stomach pain"],
  diarrhea: ["atisara", "atisar", "dast", "loose motions", "loose stools", "diarrhoea"],
  "loose motions": ["atisara", "dast", "loose stools", "diarrhea"],
  dysentery: ["pravahika", "pechish", "blood in stool"],
  vomiting: ["chardi", "chhardi", "vaman", "ulti", "emesis"],
  nausea: ["hrillasa", "ji michlana", "mitli", "queasiness"],
  constipation: ["vibandha", "malabaddhata", "kabz", "hard stool"],
  "skin disease": ["kushtha", "kushtha roga", "twak roga", "charmaroga", "skin allergy"],
  "skin rash": ["twak vikara", "kotha", "rash", "redness", "eruption"],
  itching: ["kandu", "kanduti", "khujli", "pruritus"],
  diabetes: ["prameha", "madhumeha", "sugar", "high sugar"],
  jaundice: ["kamala", "piliya", "icterus", "yellow eyes", "liver disorder"],
  anemia: ["pandu", "panduroga", "khoon ki kami", "anaemia", "low hemoglobin"],
  "back pain": ["katishoola", "kati shoola", "prishthashoola", "kamar dard", "backache", "lower back pain"],
  sciatica: ["gridhrasi", "sciatica", "leg pain", "radiculopathy"],
  "neck pain": ["manyastambha", "cervical spondylosis", "gardan dard"],
  "knee pain": ["janushoola", "ghutne ka dard"],
  "body pain": ["angamarda", "sarvanga shoola", "badan dard", "body ache", "generalized pain"],
  fatigue: ["klama", "daurbalya", "thakan", "kamzori", "tiredness", "exhaustion"],
  weakness: ["daurbalya", "kamzori", "debility", "lethargy", "fatigue"],
  insomnia: ["anidra", "nidranasha", "neend na aana", "sleeplessness"],
  hypertension: ["uccha raktachapa", "raktavata", "high bp", "high blood pressure"],
  piles: ["arsha", "arsh", "bawasir", "hemorrhoids"],
  swelling: ["shotha", "shoth", "soojan", "edema", "oedema"],
  edema: ["shotha", "swelling", "soojan"],
  "burning urination": ["mutrakrichhra", "mutradaha", "peshab me jalan", "dysuria", "uti"],
  "urinary infection": ["mutrakrichhra", "mutra roga", "uti", "urine infection"],
  "kidney stone": ["ashmari", "pathri", "renal calculi"],
  paralysis: ["pakshaghata", "pakshavadha", "lakwa", "hemiplegia"],
  fainting: ["murcha", "moorchha", "behoshi", "syncope", "loss of consciousness"],
  dizziness: ["bhrama", "chakkar", "vertigo", "giddiness"],
};

function expandSearchTerms(query) {
  const terms = new Set();
  const cleaned = query.trim().toLowerCase();
  if (!cleaned) return terms;

  terms.add(cleaned);
  cleaned.split(/\s+/).forEach((w) => {
    if (w.length >= 2) terms.add(w);
  });

  // Expand bidirectional synonyms
  for (const [engTerm, synList] of Object.entries(SYMPTOM_SYNONYMS)) {
    const allRelated = [engTerm, ...synList.map((s) => s.toLowerCase())];
    const isMatched = Array.from(terms).some((term) =>
      allRelated.some((r) => r.includes(term) || term.includes(r))
    );
    if (isMatched) {
      allRelated.forEach((item) => terms.add(item));
    }
  }

  return terms;
}

function initIntakeSearch() {
  const searchInput = document.getElementById("patient-search-input");
  const clearBtn = document.getElementById("clear-search-btn");
  const resetBtn = document.getElementById("reset-search-state-btn");
  const rows = document.querySelectorAll("tr.intake-row");
  const noResultsDiv = document.getElementById("no-search-results");

  if (!searchInput) return;

  function applyFilter() {
    const rawQuery = searchInput.value.trim().toLowerCase();

    // Toggle clear button visibility
    if (clearBtn) {
      if (rawQuery.length > 0) {
        clearBtn.classList.remove("hidden");
      } else {
        clearBtn.classList.add("hidden");
      }
    }

    if (!rows.length) return;

    if (!rawQuery) {
      rows.forEach((row) => (row.style.display = ""));
      if (noResultsDiv) noResultsDiv.classList.add("hidden");
      return;
    }

    const queryTerms = Array.from(expandSearchTerms(rawQuery));
    let visibleCount = 0;

    rows.forEach((row) => {
      const searchData = (row.getAttribute("data-search") || "").toLowerCase();
      // Match raw substring OR any expanded English/Ayurvedic synonym
      const matches =
        searchData.includes(rawQuery) ||
        queryTerms.some((term) => term.length >= 2 && searchData.includes(term));

      if (matches) {
        row.style.display = "";
        visibleCount++;
      } else {
        row.style.display = "none";
      }
    });

    if (noResultsDiv) {
      if (visibleCount === 0) {
        noResultsDiv.classList.remove("hidden");
      } else {
        noResultsDiv.classList.add("hidden");
      }
    }
  }

  // Instant real-time filtering on input
  searchInput.addEventListener("input", applyFilter);

  // Clear button click
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      searchInput.value = "";
      applyFilter();
      searchInput.focus();
    });
  }

  // Reset button in empty state
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      searchInput.value = "";
      applyFilter();
      searchInput.focus();
    });
  }

  // Escape key clears search
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      searchInput.value = "";
      applyFilter();
    }
  });

  // Quick symptom suggestion buttons
  document.querySelectorAll(".quick-symptom-tag").forEach((btn) => {
    btn.addEventListener("click", () => {
      const term = btn.getAttribute("data-term");
      if (term) {
        searchInput.value = term;
        applyFilter();
        searchInput.focus();
      }
    });
  });

  // If initial input already has value (e.g. from server-side query), run initial filter
  if (searchInput.value.trim()) {
    applyFilter();
  }

  if (window.lucide) lucide.createIcons();
}
