/**
 * static/js/patient_portal.js
 *
 * Patient-facing portal: Symptom selection, interactive AI consultation with Dr. Ayurveda,
 * and transmission of structured clinical report to the doctor dashboard.
 */

document.addEventListener("DOMContentLoaded", () => {
  initPatientPortal();
});

function initPatientPortal() {
  // State
  const state = {
    currentStep: 1,
    selectedSymptoms: new Set(),
    chatHistory: [],
    patientInfo: {
      fullName: "",
      phone: "",
      abha: "",
      age: "",
      gender: "male",
      notes: "",
    },
    isEmergency: false,
    intakeId: null,
  };

  // Elements - Step containers
  const step1 = document.getElementById("portal-step-1");
  const step2 = document.getElementById("portal-step-2");
  const step3 = document.getElementById("portal-step-3");

  // Stepper pills
  const pill1 = document.getElementById("step-pill-1");
  const pill2 = document.getElementById("step-pill-2");
  const pill3 = document.getElementById("step-pill-3");

  // Inputs
  const nameInput = document.getElementById("patient-name-input");
  const phoneInput = document.getElementById("patient-phone-input");
  const abhaInput = document.getElementById("patient-abha-input");
  const ageInput = document.getElementById("patient-age-input");
  const genderInput = document.getElementById("patient-gender-input");
  const notesInput = document.getElementById("patient-notes-input");

  // Chat elements
  const chatMessages = document.getElementById("portal-chat-messages");
  const chatForm = document.getElementById("portal-chat-form");
  const chatInput = document.getElementById("portal-chat-input");
  const emergencyBanner = document.getElementById("portal-emergency-banner");

  // Buttons
  const gotoStep2Btn = document.getElementById("btn-goto-step-2");
  const backToStep1Btn = document.getElementById("btn-back-to-step-1");
  const finalizeSendBtn = document.getElementById("btn-finalize-and-send");
  const finalizeSendBottomBtn = document.getElementById("btn-finalize-and-send-bottom");
  const newConsultationBtn = document.getElementById("btn-new-consultation");

  // Display fields
  const activeNameDisplay = document.getElementById("active-patient-name-display");
  const activeSymptomsDisplay = document.getElementById("active-patient-symptoms-display");

  // ============================================================
  // 1. Symptom Chip Selection
  // ============================================================
  document.querySelectorAll(".symptom-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const symptom = chip.getAttribute("data-symptom");
      if (state.selectedSymptoms.has(symptom)) {
        state.selectedSymptoms.delete(symptom);
        chip.classList.remove("bg-emerald-700", "text-white", "border-emerald-700");
        chip.classList.add("bg-white", "text-slate-700", "border-slate-200");
      } else {
        state.selectedSymptoms.add(symptom);
        chip.classList.remove("bg-white", "text-slate-700", "border-slate-200");
        chip.classList.add("bg-emerald-700", "text-white", "border-emerald-700");
      }
    });
  });

  // ============================================================
  // 2. Stepper Navigation
  // ============================================================
  function updateStepUI(stepNumber) {
    state.currentStep = stepNumber;

    step1.classList.toggle("hidden", stepNumber !== 1);
    step2.classList.toggle("hidden", stepNumber !== 2);
    step3.classList.toggle("hidden", stepNumber !== 3);

    // Pill styling
    const activePillClass = ["bg-emerald-700", "text-white", "shadow-xs"];
    const inactivePillClass = ["bg-slate-100", "text-slate-500"];
    const completedPillClass = ["bg-emerald-100", "text-emerald-800"];

    [pill1, pill2, pill3].forEach((p, idx) => {
      const num = idx + 1;
      p.classList.remove(...activePillClass, ...inactivePillClass, ...completedPillClass);
      if (num === stepNumber) {
        p.classList.add(...activePillClass);
      } else if (num < stepNumber) {
        p.classList.add(...completedPillClass);
      } else {
        p.classList.add(...inactivePillClass);
      }
    });

    if (window.lucide) lucide.createIcons();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // Continue to Step 2
  if (gotoStep2Btn) {
    gotoStep2Btn.addEventListener("click", () => {
      const name = nameInput.value.trim();
      const phone = phoneInput.value.trim();

      if (!name) {
        nameInput.focus();
        nameInput.classList.add("ring-2", "ring-red-400");
        return;
      }
      nameInput.classList.remove("ring-2", "ring-red-400");

      if (!phone) {
        phoneInput.focus();
        phoneInput.classList.add("ring-2", "ring-red-400");
        return;
      }
      phoneInput.classList.remove("ring-2", "ring-red-400");

      state.patientInfo.fullName = name;
      state.patientInfo.phone = phone;
      state.patientInfo.abha = abhaInput.value.trim();
      state.patientInfo.age = ageInput.value.trim();
      state.patientInfo.gender = genderInput.value;
      state.patientInfo.notes = notesInput.value.trim();

      // Update active displays
      if (activeNameDisplay) activeNameDisplay.textContent = name;
      const symptomsList = Array.from(state.selectedSymptoms);
      if (activeSymptomsDisplay) {
        activeSymptomsDisplay.textContent = symptomsList.length
          ? "Symptoms: " + symptomsList.join(", ")
          : "Symptoms: None pre-selected";
      }

      updateStepUI(2);

      // If user provided symptoms or notes and hasn't started consultation yet, send initial prompt
      if (state.chatHistory.length === 0 && (symptomsList.length > 0 || state.patientInfo.notes)) {
        let initialPrompt = "I am reporting the following symptoms:";
        if (symptomsList.length > 0) initialPrompt += " " + symptomsList.join(", ") + ".";
        if (state.patientInfo.notes) initialPrompt += " Additional details: " + state.patientInfo.notes;

        sendChatMessage(initialPrompt, false);
      }
    });
  }

  // Back to Step 1
  if (backToStep1Btn) {
    backToStep1Btn.addEventListener("click", () => {
      updateStepUI(1);
    });
  }

  // ============================================================
  // 3. AI Consultation Chat
  // ============================================================
  if (chatForm) {
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const message = chatInput.value.trim();
      if (!message) return;
      chatInput.value = "";
      sendChatMessage(message, true);
    });
  }

  async function sendChatMessage(messageText, isVisibleUserMessage = true) {
    if (isVisibleUserMessage) {
      appendChatMessage(messageText, "user");
    }

    // Thinking indicator
    const thinkingEl = document.createElement("div");
    thinkingEl.className = "flex justify-start";
    thinkingEl.innerHTML = `
      <div class="px-4 py-3 rounded-2xl bg-white border border-emerald-900/15 shadow-xs flex items-center gap-2">
        <div class="w-2 h-2 rounded-full bg-emerald-600 animate-bounce"></div>
        <div class="w-2 h-2 rounded-full bg-emerald-600 animate-bounce" style="animation-delay: 0.15s"></div>
        <div class="w-2 h-2 rounded-full bg-emerald-600 animate-bounce" style="animation-delay: 0.3s"></div>
        <span class="text-xs text-slate-500 font-medium ml-1">Dr. Ayurveda is thinking...</span>
      </div>
    `;
    chatMessages.appendChild(thinkingEl);
    scrollChatBottom();

    try {
      const response = await fetch("/patient-portal/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_message: messageText,
          chat_history: state.chatHistory,
          mobile_number: state.patientInfo.phone,
          abha_id: state.patientInfo.abha,
        }),
      });

      thinkingEl.remove();

      if (!response.ok) {
        appendChatMessage("Sorry, I encountered an issue processing that. Please try again.", "assistant");
        scrollChatBottom();
        return;
      }

      const data = await response.json();
      state.chatHistory = data.chat_history || state.chatHistory;

      if (data.is_emergency) {
        state.isEmergency = true;
        if (emergencyBanner) emergencyBanner.classList.remove("hidden");
      }

      appendChatMessage(data.ai_response, "assistant");
      scrollChatBottom();
    } catch (err) {
      console.error("Chat error:", err);
      thinkingEl.remove();
      appendChatMessage("Could not reach Dr. Ayurveda. Please check your connection and try again.", "assistant");
      scrollChatBottom();
    }
  }

  function appendChatMessage(text, role) {
    const msgEl = document.createElement("div");
    msgEl.className = `flex ${role === "user" ? "justify-end" : "justify-start"}`;

    const formattedText = formatMarkdownSnippet(text);

    msgEl.innerHTML = `
      <div class="max-w-md lg:max-w-xl px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-xs
        ${
          role === "user"
            ? "bg-emerald-700 text-white rounded-br-xs"
            : "bg-white border border-emerald-900/15 text-slate-800 rounded-bl-xs"
        }">
        ${formattedText}
      </div>
    `;
    chatMessages.appendChild(msgEl);
  }

  function scrollChatBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function formatMarkdownSnippet(text) {
    if (!text) return "";
    return text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/\n\n/g, "<br><br>")
      .replace(/\n/g, "<br>");
  }

  // ============================================================
  // 4. Finalize & Submit Report to Doctor
  // ============================================================
  async function finalizeAndSendReport() {
    if (state.chatHistory.length === 0) {
      alert("Please chat with Dr. Ayurveda first to describe your condition before sending.");
      return;
    }

    const btns = [finalizeSendBtn, finalizeSendBottomBtn].filter(Boolean);
    btns.forEach((b) => {
      b.disabled = true;
      b.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Sending Report...</span>`;
    });
    if (window.lucide) lucide.createIcons();

    try {
      const response = await fetch("/patient-portal/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: state.patientInfo.fullName,
          mobile_number: state.patientInfo.phone,
          abha_id: state.patientInfo.abha,
          symptoms: Array.from(state.selectedSymptoms),
          symptom_notes: state.patientInfo.notes,
          chat_history: state.chatHistory,
          is_emergency: state.isEmergency,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        alert("Submission failed: " + (err.error || "Please try again."));
        return;
      }

      const data = await response.json();
      state.intakeId = data.intake_id;

      // Populate Receipt Screen
      const receiptIdEl = document.getElementById("receipt-intake-id");
      const receiptNameEl = document.getElementById("receipt-patient-name");
      const receiptBadgeEl = document.getElementById("receipt-priority-badge");
      const receiptSummaryEl = document.getElementById("receipt-summary-text");

      if (receiptIdEl) receiptIdEl.textContent = data.intake_id ? `#${data.intake_id.slice(0, 8)}` : "Submitted";
      if (receiptNameEl) receiptNameEl.textContent = state.patientInfo.fullName;

      if (receiptBadgeEl) {
        if (data.triage_priority === "high" || data.is_emergency) {
          receiptBadgeEl.className = "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200";
          receiptBadgeEl.textContent = "High Priority";
        } else {
          receiptBadgeEl.className = "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200";
          receiptBadgeEl.textContent = "Routine";
        }
      }

      if (receiptSummaryEl) {
        const narrative = data.report?.ai_assessment?.narrative;
        receiptSummaryEl.textContent = narrative || "Consultation complete. Intake assessment delivered to clinic portal.";
      }

      updateStepUI(3);
    } catch (err) {
      console.error("Submission error:", err);
      alert("An error occurred while transmitting your report. Please try again.");
    } finally {
      btns.forEach((b) => {
        b.disabled = false;
        b.innerHTML = `<i data-lucide="send" class="w-3.5 h-3.5"></i><span>Send Report to Doctor</span>`;
      });
      if (window.lucide) lucide.createIcons();
    }
  }

  if (finalizeSendBtn) finalizeSendBtn.addEventListener("click", finalizeAndSendReport);
  if (finalizeSendBottomBtn) finalizeSendBottomBtn.addEventListener("click", finalizeAndSendReport);

  // Reset for new consultation
  if (newConsultationBtn) {
    newConsultationBtn.addEventListener("click", () => {
      // Reset form
      nameInput.value = "";
      phoneInput.value = "";
      abhaInput.value = "";
      ageInput.value = "";
      notesInput.value = "";
      state.selectedSymptoms.clear();
      state.chatHistory = [];
      state.isEmergency = false;
      state.intakeId = null;

      document.querySelectorAll(".symptom-chip").forEach((chip) => {
        chip.classList.remove("bg-emerald-700", "text-white", "border-emerald-700");
        chip.classList.add("bg-white", "text-slate-700", "border-slate-200");
      });

      if (emergencyBanner) emergencyBanner.classList.add("hidden");

      // Reset chat messages to welcome message
      chatMessages.innerHTML = `
        <div class="flex justify-start">
          <div class="max-w-md lg:max-w-xl px-4 py-3 rounded-2xl text-sm bg-white border border-emerald-900/15 text-slate-800 shadow-xs leading-relaxed space-y-2">
            <p class="font-semibold text-emerald-800 text-xs flex items-center gap-1.5">
              <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
              Namaste! I am Dr. Ayurveda.
            </p>
            <p>
              I am here to understand what you are going through before you meet the treating physician. 
              Please describe your symptoms, how long you've had them, your appetite, and how you are feeling overall.
            </p>
            <p class="text-xs text-slate-500 pt-1 border-t border-slate-100">
              When we finish, I will prepare a complete structured clinical report and send it directly to your doctor.
            </p>
          </div>
        </div>
      `;

      updateStepUI(1);
    });
  }
}
