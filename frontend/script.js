"use strict";

/* =================================================================
   Local Search Engine — script.js
   Vanilla browser JavaScript only. Talks to the existing backend
   through fetch(); performs no scanning, indexing, or ranking here.
   ================================================================= */

document.addEventListener("DOMContentLoaded", () => {

  /* -----------------------------------------------------------
     Element references
     ----------------------------------------------------------- */
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("search-input");
  const indexBtn = document.getElementById("index-btn");
  const statsBtn = document.getElementById("stats-btn");
  const statusMessage = document.getElementById("status-message");

  const statDocuments = document.getElementById("stat-documents");
  const statTerms = document.getElementById("stat-terms");
  const statSize = document.getElementById("stat-size");
  const statLastRun = document.getElementById("stat-last-run");

  const resultsList = document.getElementById("results-list");
  const resultsCount = document.getElementById("results-count");
  const resultTemplate = document.getElementById("result-card-template");

  /* -----------------------------------------------------------
     Small helpers
     ----------------------------------------------------------- */

  // Escape HTML so backend-supplied text (filenames, paths, snippets)
  // can never be interpreted as markup.
  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = String(value ?? "");
    return div.innerHTML;
  }

  // Set the top status line. state: "" | "loading" | "success" | "error"
  function setStatus(message, state = "") {
    statusMessage.textContent = message;
    statusMessage.classList.remove("is-loading", "is-success", "is-error");
    if (state) {
      statusMessage.classList.add(`is-${state}`);
    }
  }

  // Replace the results list with a single centered message
  // (used for empty state, loading, no-results, and errors).
  function setResultsState(message, state = "") {
    resultsList.innerHTML = "";
    const li = document.createElement("li");
    li.className = "state-message";
    if (state) {
      li.classList.add(`is-${state}`);
    }
    li.textContent = message;
    resultsList.appendChild(li);
  }

  function setResultsCount(count) {
    if (count === null) {
      resultsCount.textContent = "";
    } else if (count === 0) {
      resultsCount.textContent = "No results";
    } else if (count === 1) {
      resultsCount.textContent = "1 result";
    } else {
      resultsCount.textContent = `${count} results`;
    }
  }

  function formatBytes(bytes) {
    if (typeof bytes !== "number" || Number.isNaN(bytes)) {
      return "-";
    }
    if (bytes === 0) {
      return "0 B";
    }
    const units = ["B", "KB", "MB", "GB", "TB"];
    const exponent = Math.min(
      Math.floor(Math.log(bytes) / Math.log(1024)),
      units.length - 1
    );
    const value = bytes / Math.pow(1024, exponent);
    const decimals = exponent === 0 ? 0 : 1;
    return `${value.toFixed(decimals)} ${units[exponent]}`;
  }

  // last_run is an object, not a string — turn it into one readable value.
  function formatLastRun(lastRun) {
    if (!lastRun || typeof lastRun !== "object") {
      return "-";
    }
    if (lastRun.run_id !== undefined && lastRun.run_id !== null) {
      return `Run #${lastRun.run_id}`;
    }
    if (lastRun.started_at) {
      const date = new Date(lastRun.started_at * 1000);
      if (!Number.isNaN(date.getTime())) {
        return date.toLocaleString();
      }
    }
    return "-";
  }

  function formatNumber(value) {
    if (typeof value !== "number" || Number.isNaN(value)) {
      return "-";
    }
    return value.toLocaleString();
  }

  // Turn "**term**" markers from the backend snippet into safe <mark> tags.
  // The text is escaped FIRST, so only our own <mark> tags become markup —
  // anything the backend/file content contained stays inert text.
  function highlightSnippet(rawSnippet) {
    const escaped = escapeHtml(rawSnippet);
    return escaped.replace(/\*\*(.+?)\*\*/g, "<mark>$1</mark>");
  }

  // Wrapper around fetch() with consistent error handling.
  // Never throws — always resolves to { ok, data, error }.
  async function fetchJson(url, options) {
    let response;
    try {
      response = await fetch(url, options);
    } catch (networkError) {
      return { ok: false, data: null, error: "Could not connect to the search server." };
    }

    let data;
    try {
      data = await response.json();
    } catch (parseError) {
      return { ok: false, data: null, error: "The server sent an invalid response." };
    }

    if (!response.ok || data.success === false) {
      return { ok: false, data, error: data.error || "Something went wrong." };
    }

    return { ok: true, data, error: null };
  }

  /* -----------------------------------------------------------
     Search
     ----------------------------------------------------------- */

  async function performSearch(query) {
    const trimmed = query.trim();

    if (!trimmed) {
      setStatus("Please enter a search term.");
      return;
    }

    setStatus("Searching...", "loading");
    setResultsState("Searching...", "loading");
    setResultsCount(null);

    const url = "/api/search?q=" + encodeURIComponent(trimmed);
    const { ok, data, error } = await fetchJson(url);

    if (!ok) {
      setStatus(error, "error");
      setResultsState(error, "error");
      return;
    }

    const results = Array.isArray(data.results) ? data.results : [];
    renderResults(results);
    setResultsCount(results.length);
    setStatus("Search completed.", "success");
  }

  function renderResults(results) {
    resultsList.innerHTML = "";

    if (results.length === 0) {
      setResultsState("No matching files found.");
      return;
    }

    for (const result of results) {
      resultsList.appendChild(buildResultCard(result));
    }
  }

  function buildResultCard(result) {
    const node = resultTemplate.content.firstElementChild.cloneNode(true);

    const filename = result.filename || "";
    const fileType = result.file_type || "";
    const filepath = result.filepath || "";
    const snippet = result.snippet || "";
    const score = typeof result.score === "number" ? result.score : 0;

    // Text-only fields go through textContent — never innerHTML — so
    // there is no way for backend-supplied text to inject markup.
    node.querySelector(".result-card__filename").textContent = filename;
    node.querySelector(".result-card__filetype").textContent = fileType;
    node.querySelector(".result-card__filepath").textContent = filepath;

    // Snippet is the one field that needs markup (the highlight marks),
    // so it goes through the escape-then-highlight helper instead.
    node.querySelector(".result-card__snippet").innerHTML = highlightSnippet(snippet);

    const stampEl = node.querySelector(".result-card__stamp");
    const stampValueEl = node.querySelector(".result-card__stamp-value");
    const clampedScore = Math.max(0, Math.min(100, score));
    stampEl.style.setProperty("--relevance", `${clampedScore}%`);
    stampValueEl.textContent = `${score.toFixed(1)}%`;

    const openBtn = node.querySelector(".result-card__open-btn");
    openBtn.addEventListener("click", () => openFile(filepath));

    return node;
  }

  async function openFile(filepath) {
    if (!filepath) {
      return;
    }

    setStatus(`Opening ${filepath}...`, "loading");

    const url = "/api/open?path=" + encodeURIComponent(filepath);
    const { ok, error } = await fetchJson(url);

    if (!ok) {
      setStatus(error, "error");
      return;
    }

    setStatus("File opened.", "success");
  }

  /* -----------------------------------------------------------
     Index / Update
     ----------------------------------------------------------- */

  async function runIndex() {
    indexBtn.disabled = true;
    indexBtn.setAttribute("aria-busy", "true");
    setStatus("Scanning and indexing...", "loading");

    const { ok, data, error } = await fetchJson("/api/index", { method: "POST" });

    indexBtn.disabled = false;
    indexBtn.removeAttribute("aria-busy");

    if (!ok) {
      setStatus(error, "error");
      return;
    }

    const indexed = data.files_indexed ?? 0;
    const fileWord = indexed === 1 ? "file" : "files";
    setStatus(`Indexing complete. ${indexed} new/modified ${fileWord} indexed.`, "success");

    await loadStatistics();
  }

  /* -----------------------------------------------------------
     Statistics
     ----------------------------------------------------------- */

  async function loadStatistics() {
    const { ok, data, error } = await fetchJson("/api/statistics");

    if (!ok) {
      statDocuments.textContent = "-";
      statTerms.textContent = "-";
      statSize.textContent = "-";
      statLastRun.textContent = "-";
      setStatus(error, "error");
      return;
    }

    const stats = data.statistics || {};

    statDocuments.textContent = formatNumber(stats.documents_indexed);
    statTerms.textContent = formatNumber(stats.unique_terms);
    statSize.textContent = formatBytes(stats.database_size_bytes);
    statLastRun.textContent = formatLastRun(stats.last_run);
  }

  /* -----------------------------------------------------------
     Event wiring
     ----------------------------------------------------------- */

  // Form submit covers both the Search button click AND pressing
  // Enter inside the search input — no separate keydown handler needed.
  searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    performSearch(searchInput.value);
  });

  indexBtn.addEventListener("click", () => {
    runIndex();
  });

  statsBtn.addEventListener("click", () => {
    setStatus("Loading statistics...", "loading");
    loadStatistics().then(() => setStatus("Statistics updated.", "success"));
  });

  /* -----------------------------------------------------------
     Initial load
     ----------------------------------------------------------- */
  setStatus("Ready. Enter a search term.");
  loadStatistics();
});
