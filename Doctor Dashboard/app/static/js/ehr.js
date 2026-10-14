/**
 * static/js/ehr.js
 *
 * Everything here is purely client-side UI polish — no fetch(), no AJAX.
 * The actual save happens via a normal HTML form POST to /ehr/save, and the
 * FHIR JSON / vector mappings are already rendered server-side into the page.
 */
document.addEventListener("DOMContentLoaded", () => {
  // ---- Sample note loader ------------------------------------------------
  const sampleNote = `Patient presents with complaints of chronic Amlapitta (hyperacidity) accompanied by Mandagni (reduced digestive power) over the last 3 weeks. Morning joint stiffness noticed in distal joints. Prescribed Sutshekhar Ras 250mg BID after meals.`;

  const loadSampleBtn = document.getElementById("load-sample-btn");
  const clinicalNotes = document.getElementById("clinical-notes");
  if (loadSampleBtn && clinicalNotes) {
    loadSampleBtn.addEventListener("click", () => {
      clinicalNotes.value = sampleNote;
    });
  }

  // ---- Tag chips ------------------------------------------------------------
  // Visible chips are just for display; the actual value submitted with the
  // form lives in the hidden #manual-tags-field as a comma-separated string.
  const tagInput = document.getElementById("tag-input");
  const addTagBtn = document.getElementById("add-tag-btn");
  const chipContainer = document.getElementById("tag-chip-container");
  const manualTagsField = document.getElementById("manual-tags-field");

  function currentTags() {
    return manualTagsField.value
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
  }

  function renderChips() {
    chipContainer.innerHTML = "";
    currentTags().forEach((tag, index) => {
      const chip = document.createElement("span");
      chip.className =
        "inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs bg-emerald-50 text-emerald-800 border border-emerald-200 font-mono";
      chip.innerHTML = `${escapeHtml(tag)} <button type="button" class="hover:text-red-500 ml-1" data-index="${index}">×</button>`;
      chipContainer.appendChild(chip);
    });
  }

  function addTag(value) {
    const trimmed = value.trim();
    if (!trimmed) return;
    const tags = currentTags();
    tags.push(trimmed);
    manualTagsField.value = tags.join(", ");
    renderChips();
  }

  if (addTagBtn && tagInput) {
    addTagBtn.addEventListener("click", () => {
      addTag(tagInput.value);
      tagInput.value = "";
    });
  }

  if (chipContainer) {
    chipContainer.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-index]");
      if (!btn) return;
      const tags = currentTags();
      tags.splice(Number(btn.dataset.index), 1);
      manualTagsField.value = tags.join(", ");
      renderChips();
    });
  }

  if (manualTagsField) renderChips();

  // ---- FHIR / Vector Mapping tabs -------------------------------------------
  const tabFhir = document.getElementById("tab-fhir");
  const tabMapping = document.getElementById("tab-mapping");
  const panelFhir = document.getElementById("panel-fhir");
  const panelMapping = document.getElementById("panel-mapping");

  if (tabFhir && tabMapping) {
    tabFhir.addEventListener("click", () => {
      tabFhir.className = "px-3 py-1 rounded-md bg-white text-emerald-800 shadow-xs font-medium";
      tabMapping.className = "px-3 py-1 rounded-md text-slate-500 hover:text-slate-800";
      panelFhir.classList.remove("hidden");
      panelMapping.classList.add("hidden");
    });
    tabMapping.addEventListener("click", () => {
      tabMapping.className = "px-3 py-1 rounded-md bg-white text-emerald-800 shadow-xs font-medium";
      tabFhir.className = "px-3 py-1 rounded-md text-slate-500 hover:text-slate-800";
      panelMapping.classList.remove("hidden");
      panelFhir.classList.add("hidden");
    });
  }

  // ---- Copy FHIR JSON ------------------------------------------------------
  const copyBtn = document.getElementById("copy-fhir-btn");
  const fhirOutput = document.getElementById("fhir-output");
  if (copyBtn && fhirOutput) {
    copyBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(fhirOutput.textContent);
    });
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
});
