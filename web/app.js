/* =========================================================
   FLORAFIND
   ZERO-DEPENDENCY FRONTEND LOGIC
   ========================================================= */

"use strict";


/* =========================================================
   DOM REFERENCES
   ========================================================= */

const searchInput =
    document.getElementById("search-input");

const clearBtn =
    document.getElementById("clear-btn");

const resultsContainer =
    document.getElementById("results-container");

const resultsMeta =
    document.getElementById("results-meta");

const resultCount =
    document.getElementById("result-count");

const searchTime =
    document.getElementById("search-time");

const statsInfo =
    document.getElementById("stats-info");

const reindexBtn =
    document.getElementById("reindex-btn");

const updateText =
    document.getElementById("update-text");

const statusDot =
    document.getElementById("status-dot");

const statusIcon =
    document.getElementById("status-icon");

const toast =
    document.getElementById("toast");

const filterPills =
    document.querySelectorAll(".filter-pill");

const exampleChips =
    document.querySelectorAll(".example-chip");


/* =========================================================
   STATE
   ========================================================= */

let activeFilter = "all";

let debounceTimer = null;

let toastTimer = null;

let statsTimer = null;

let currentSearchController = null;


/* =========================================================
   CONSTANTS
   ========================================================= */

const EMPTY_MESSAGE =
    "Search for a topic, phrase, programming concept, note, or anything you remember from your files.";


/* =========================================================
   SEARCH INPUT
   ========================================================= */

searchInput.addEventListener(
    "input",
    function (event) {

        const query =
            event.target.value.trim();

        clearBtn.style.display =
            query.length > 0
                ? "block"
                : "none";

        clearTimeout(debounceTimer);

        if (!query) {

            showWelcome();

            return;
        }

        debounceTimer =
            setTimeout(
                function () {
                    performSearch(
                        query,
                        activeFilter
                    );
                },
                250
            );
    }
);


/* =========================================================
   CLEAR SEARCH
   ========================================================= */

clearBtn.addEventListener(
    "click",
    function () {

        searchInput.value = "";

        clearBtn.style.display = "none";

        if (currentSearchController) {
            currentSearchController.abort();
            currentSearchController = null;
        }

        showWelcome();

        searchInput.focus();
    }
);


/* =========================================================
   FILTERS
   ========================================================= */

filterPills.forEach(
    function (pill) {

        pill.addEventListener(
            "click",
            function () {

                filterPills.forEach(
                    function (item) {
                        item.classList.remove(
                            "active"
                        );
                    }
                );

                pill.classList.add("active");

                activeFilter =
                    pill.dataset.filter || "all";

                const query =
                    searchInput.value.trim();

                if (query) {

                    performSearch(
                        query,
                        activeFilter
                    );

                } else {

                    showWelcome();
                }
            }
        );
    }
);


/* =========================================================
   EXAMPLE SEARCHES
   ========================================================= */

exampleChips.forEach(
    function (chip) {

        chip.addEventListener(
            "click",
            function () {

                const query =
                    chip.dataset.query || "";

                searchInput.value = query;

                clearBtn.style.display =
                    "block";

                performSearch(
                    query,
                    activeFilter
                );
            }
        );
    }
);


/* =========================================================
   SEARCH
   ========================================================= */

async function performSearch(
    query,
    filter
) {

    if (!query) {
        showWelcome();
        return;
    }

    if (currentSearchController) {
        currentSearchController.abort();
    }

    currentSearchController =
        new AbortController();

    const started =
        performance.now();

    showLoading();

    try {

        const url =
            `/api/search?q=${encodeURIComponent(query)}` +
            `&type=${encodeURIComponent(filter)}`;

        const response =
            await fetch(
                url,
                {
                    method: "GET",
                    cache: "no-store",
                    signal:
                        currentSearchController.signal
                }
            );

        if (!response.ok) {

            throw new Error(
                `Server returned ${response.status}`
            );
        }

        const data =
            await response.json();

        const elapsed =
            performance.now() - started;

        if (data.error) {

            showError(
                data.error
            );

            return;
        }

        const results =
            Array.isArray(data.results)
                ? data.results
                : [];

        renderResults(
            results,
            query,
            elapsed
        );

    } catch (error) {

        if (
            error.name === "AbortError"
        ) {
            return;
        }

        console.error(
            "Search error:",
            error
        );

        showError(
            "Could not connect to the search server. " +
            "Make sure web_app.py is running."
        );

    } finally {

        currentSearchController = null;
    }
}


/* =========================================================
   RENDER RESULTS
   ========================================================= */

function renderResults(
    results,
    query,
    elapsed
) {

    resultsMeta.classList.remove(
        "hidden"
    );

    resultCount.textContent =
        results.length.toString();

    searchTime.textContent =
        `${elapsed.toFixed(1)} ms`;

    if (!results.length) {

        resultsContainer.innerHTML = `

            <div class="empty-state">

                <div class="empty-icon">
                    🌷
                </div>

                <h3>
                    No matching files found
                </h3>

                <p>
                    Nothing matched
                    "<strong>${escapeHtml(query)}</strong>".
                    Try fewer keywords, another phrase,
                    or a different file type.
                </p>

            </div>
        `;

        return;
    }

    resultsContainer.innerHTML =
        results
            .map(
                function (item) {
                    return createResultCard(
                        item,
                        query
                    );
                }
            )
            .join("");
}


/* =========================================================
   RESULT CARD
   ========================================================= */

function createResultCard(
    item,
    query
) {

    const filename =
        escapeHtml(
            item.filename || "Unnamed file"
        );

    const filepath =
        escapeHtml(
            item.filepath || ""
        );

    const fileType =
        escapeHtml(
            item.file_type || "file"
        );

    const relevance =
        Number.isFinite(
            Number(item.relevance)
        )
            ? Number(item.relevance).toFixed(1)
            : "0.0";

    const snippet =
        item.snippet ||
        "No text snippet available.";

    const size =
        formatFileSize(
            Number(item.size_bytes || 0)
        );

    const safePath =
        encodeURIComponent(
            item.filepath || ""
        );

    return `

        <article class="result-card">

            <div class="card-top">

                <div class="file-heading">

                    <a
                        href="#"
                        class="file-link"
                        data-filepath="${safePath}"
                    >
                        📄 ${filename}
                    </a>

                    <div class="file-path">
                        ${filepath}
                    </div>

                </div>

                <div class="badge-group">

                    <span class="score-badge">
                        ${relevance}% match
                    </span>

                    <span class="type-badge">
                        ${fileType}
                    </span>

                </div>

            </div>


            <div class="snippet-box">

                ${highlightKeywords(
                    escapeHtml(snippet),
                    query
                )}

            </div>


            <div class="card-footer">

                <span>
                    Size: ${size}
                </span>

                <button
                    class="open-action"
                    type="button"
                    data-filepath="${safePath}"
                >
                    Open File ↗
                </button>

            </div>

        </article>
    `;
}


/* =========================================================
   RESULT EVENT HANDLING
   ========================================================= */

resultsContainer.addEventListener(
    "click",
    function (event) {

        const target =
            event.target.closest(
                "[data-filepath]"
            );

        if (!target) {
            return;
        }

        event.preventDefault();

        const encodedPath =
            target.dataset.filepath;

        if (!encodedPath) {
            return;
        }

        let filepath;

        try {

            filepath =
                decodeURIComponent(
                    encodedPath
                );

        } catch {

            showToast(
                "Could not read the selected file path.",
                "error"
            );

            return;
        }

        handleOpenFile(filepath);
    }
);


/* =========================================================
   OPEN FILE
   ========================================================= */

async function handleOpenFile(
    filepath
) {

    if (!filepath) {

        showToast(
            "No file path was supplied.",
            "error"
        );

        return;
    }

    try {

        const response =
            await fetch(
                "/api/open",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        filepath: filepath
                    })
                }
            );

        const data =
            await response.json();

        if (!response.ok || data.error) {

            showToast(
                data.error ||
                "Could not open the file.",
                "error"
            );

            return;
        }

        showToast(
            "🌸 Opening file with your default application.",
            "success"
        );

    } catch (error) {

        console.error(
            "Open file error:",
            error
        );

        showToast(
            "Could not communicate with the server.",
            "error"
        );
    }
}


/* =========================================================
   UPDATE INDEX
   ========================================================= */

reindexBtn.addEventListener(
    "click",
    async function () {

        setIndexButtonBusy(
            true
        );

        try {

            const response =
                await fetch(
                    "/api/index",
                    {
                        method: "POST",
                        cache: "no-store"
                    }
                );

            const data =
                await response.json();

            if (
                data.status ===
                "already_running"
            ) {

                showToast(
                    "🌸 Indexing is already running.",
                    "success"
                );

                return;
            }

            if (!response.ok) {

                throw new Error(
                    data.error ||
                    "Could not start indexing."
                );
            }

            showToast(
                "🌸 Index update started.",
                "success"
            );

            startStatsPolling();

        } catch (error) {

            console.error(
                "Index error:",
                error
            );

            showToast(
                "Could not start the index update.",
                "error"
            );

        } finally {

            setTimeout(
                function () {

                    if (!isIndexingUI()) {

                        setIndexButtonBusy(
                            false
                        );
                    }

                },
                800
            );
        }
    }
);


/* =========================================================
   STATISTICS
   ========================================================= */

async function pollStats() {

    try {

        const response =
            await fetch(
                "/api/stats",
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {
            throw new Error(
                `Status ${response.status}`
            );
        }

        const data =
            await response.json();

        updateStatsUI(
            data
        );

        if (data.is_indexing) {

            startStatsPolling();

        } else {

            stopStatsPolling();

            setIndexButtonBusy(
                false
            );
        }

    } catch (error) {

        console.error(
            "Stats error:",
            error
        );

        statsInfo.textContent =
            "Server connection unavailable";

        statusDot.classList.remove(
            "busy"
        );

        statusDot.classList.add(
            "error"
        );

        statusIcon.textContent =
            "!";
    }
}


function updateStatsUI(
    data
) {

    const documents =
        Number(
            data.documents_indexed || 0
        );

    const uniqueTerms =
        Number(
            data.unique_terms || 0
        );

    if (data.is_indexing) {

        statsInfo.textContent =
            data.index_message ||
            "Updating index...";

        statusDot.classList.add(
            "busy"
        );

        statusDot.classList.remove(
            "error"
        );

        statusIcon.textContent =
            "✿";

        setIndexButtonBusy(
            true
        );

        return;
    }

    statusDot.classList.remove(
        "busy",
        "error"
    );

    statusIcon.textContent =
        "✿";

    if (data.index_error) {

        statsInfo.textContent =
            `Indexing error`;

        statusDot.classList.add(
            "error"
        );

        return;
    }

    if (documents === 0) {

        statsInfo.textContent =
            "No files indexed yet";

        return;
    }

    statsInfo.textContent =
        `${documents.toLocaleString()} files indexed` +
        ` • ${uniqueTerms.toLocaleString()} terms`;
}


/* =========================================================
   POLLING CONTROL
   ========================================================= */

function startStatsPolling() {

    if (statsTimer !== null) {
        return;
    }

    statsTimer =
        setInterval(
            pollStats,
            1500
        );
}


function stopStatsPolling() {

    if (statsTimer !== null) {

        clearInterval(
            statsTimer
        );

        statsTimer = null;
    }
}


/* =========================================================
   INDEX BUTTON UI
   ========================================================= */

function setIndexButtonBusy(
    busy
) {

    if (busy) {

        reindexBtn.disabled = true;

        reindexBtn.classList.add(
            "loading"
        );

        updateText.textContent =
            "Updating index...";

    } else {

        reindexBtn.disabled = false;

        reindexBtn.classList.remove(
            "loading"
        );

        updateText.textContent =
            "Update Index";
    }
}


function isIndexingUI() {

    return reindexBtn.disabled;
}


/* =========================================================
   WELCOME STATE
   ========================================================= */

function showWelcome() {

    resultsMeta.classList.add(
        "hidden"
    );

    resultsContainer.innerHTML = `

        <div class="welcome-card">

            <div class="welcome-flower">
                ❀
            </div>

            <h2>
                Your files are waiting 🌸
            </h2>

            <p>
                ${EMPTY_MESSAGE}
            </p>

            <div class="example-searches">

                <span>
                    Try searching for
                </span>

                <button
                    class="example-chip"
                    data-query="python"
                    type="button"
                >
                    python
                </button>

                <button
                    class="example-chip"
                    data-query="project"
                    type="button"
                >
                    project
                </button>

                <button
                    class="example-chip"
                    data-query="assignment"
                    type="button"
                >
                    assignment
                </button>

            </div>

        </div>
    `;

    attachDynamicExampleHandlers();
}


function attachDynamicExampleHandlers() {

    document
        .querySelectorAll(
            ".example-chip"
        )
        .forEach(
            function (chip) {

                chip.addEventListener(
                    "click",
                    function () {

                        const query =
                            chip.dataset.query || "";

                        searchInput.value =
                            query;

                        clearBtn.style.display =
                            "block";

                        performSearch(
                            query,
                            activeFilter
                        );
                    }
                );
            }
        );
}


/* =========================================================
   LOADING STATE
   ========================================================= */

function showLoading() {

    resultsMeta.classList.remove(
        "hidden"
    );

    resultCount.textContent =
        "…";

    searchTime.textContent =
        "Searching";

    resultsContainer.innerHTML = `

        <div class="loading-state">

            <div class="loading-spinner"></div>

            <span>
                Looking through your files...
            </span>

        </div>
    `;
}


/* =========================================================
   ERROR STATE
   ========================================================= */

function showError(
    message
) {

    resultsMeta.classList.add(
        "hidden"
    );

    resultsContainer.innerHTML = `

        <div class="empty-state">

            <div class="empty-icon">
                🌷
            </div>

            <h3>
                Something went wrong
            </h3>

            <p>
                ${escapeHtml(message)}
            </p>

        </div>
    `;
}


/* =========================================================
   HIGHLIGHT SEARCH TERMS
   ========================================================= */

function highlightKeywords(
    text,
    query
) {

    if (!query) {
        return text;
    }

    const terms =
        query
            .trim()
            .split(/\s+/)
            .filter(
                term => term.length > 1
            );

    if (!terms.length) {
        return text;
    }

    const escapedTerms =
        terms.map(
            function (term) {

                return term.replace(
                    /[.*+?^${}()|[\]\\]/g,
                    "\\$&"
                );
            }
        );

    const pattern =
        escapedTerms.join("|");

    const regex =
        new RegExp(
            `(${pattern})`,
            "gi"
        );

    return text.replace(
        regex,
        '<mark class="highlight">$1</mark>'
    );
}


/* =========================================================
   HTML ESCAPING
   ========================================================= */

function escapeHtml(
    value
) {

    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }

    return String(value)
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );
}


/* =========================================================
   FILE SIZE
   ========================================================= */

function formatFileSize(
    bytes
) {

    if (
        !Number.isFinite(bytes) ||
        bytes <= 0
    ) {
        return "0 B";
    }

    const units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB"
    ];

    let value = bytes;

    let index = 0;

    while (
        value >= 1024 &&
        index < units.length - 1
    ) {

        value /= 1024;

        index++;
    }

    if (index === 0) {
        return `${Math.round(value)} B`;
    }

    return `${value.toFixed(1)} ${units[index]}`;
}


/* =========================================================
   TOAST
   ========================================================= */

function showToast(
    message,
    type = "success"
) {

    clearTimeout(
        toastTimer
    );

    toast.textContent =
        message;

    toast.className =
        `toast ${type} show`;

    toastTimer =
        setTimeout(
            function () {

                toast.classList.remove(
                    "show"
                );

            },
            3300
        );
}


/* =========================================================
   INITIALIZATION
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        showWelcome();

        pollStats();

    }
);