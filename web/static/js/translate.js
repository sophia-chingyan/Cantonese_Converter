(function () {
  "use strict";

  var form = document.getElementById("translate-form");
  var providerSelect = document.getElementById("provider-select");
  var pastedText = document.getElementById("pasted-text");
  var fileInput = document.getElementById("file-input");
  var translateBtn = document.getElementById("translate-btn");
  var formError = document.getElementById("form-error");

  var progressPanel = document.getElementById("progress-panel");
  var progressHeading = document.getElementById("progress-heading");
  var cueStrip = document.getElementById("cue-strip");
  var progressNote = document.getElementById("progress-note");

  var outputPanel = document.getElementById("output-panel");
  var failureBanner = document.getElementById("failure-banner");
  var outputText = document.getElementById("output-text");
  var saveBtn = document.getElementById("save-btn");
  var saveStatus = document.getElementById("save-status");

  var currentJobId = null;
  var pollTimer = null;
  var cueStripBuilt = false;

  function showError(msg) {
    formError.textContent = msg;
    formError.hidden = false;
  }

  function clearError() {
    formError.hidden = true;
    formError.textContent = "";
  }

  function resetPanels() {
    progressPanel.hidden = true;
    outputPanel.hidden = true;
    failureBanner.hidden = true;
    cueStrip.innerHTML = "";
    saveStatus.textContent = "";
    cueStripBuilt = false;
  }

  function buildCueStrip(total) {
    cueStrip.innerHTML = "";
    for (var i = 1; i <= total; i++) {
      var badge = document.createElement("span");
      badge.className = "cue-badge";
      badge.textContent = String(i).length < 2 ? "0" + i : String(i);
      cueStrip.appendChild(badge);
    }
    cueStripBuilt = true;
  }

  function updateCueStrip(completed, total) {
    var badges = cueStrip.querySelectorAll(".cue-badge");
    for (var idx = 0; idx < badges.length; idx++) {
      var n = idx + 1;
      badges[idx].classList.toggle("is-done", n <= completed);
      badges[idx].classList.toggle("is-active", n === completed + 1 && completed < total);
    }
  }

  function fetchJson(url, options) {
    return fetch(url, options).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  form.addEventListener("submit", function (evt) {
    evt.preventDefault();
    clearError();
    resetPanels();

    var hasFile = fileInput.files && fileInput.files.length > 0;
    var hasText = pastedText.value.trim().length > 0;
    if (!hasFile && !hasText) {
      showError("Paste some text or choose a file first.");
      return;
    }

    var formData = new FormData();
    formData.append("provider", providerSelect.value);
    if (hasFile) {
      formData.append("file", fileInput.files[0]);
    } else {
      formData.append("pasted_text", pastedText.value);
    }

    translateBtn.disabled = true;
    translateBtn.textContent = "Starting…";

    fetchJson("/api/translate", { method: "POST", body: formData })
      .then(function (result) {
        if (!result.ok) {
          throw new Error(result.data.error || "Could not start translation.");
        }
        currentJobId = result.data.job_id;
        progressPanel.hidden = false;
        progressHeading.textContent = "Translating…";
        startPolling();
      })
      .catch(function (err) {
        showError(err.message);
      })
      .finally(function () {
        translateBtn.disabled = false;
        translateBtn.textContent = "Translate";
      });
  });

  function startPolling() {
    pollTimer = window.setInterval(function () {
      fetchJson("/api/jobs/" + currentJobId)
        .then(function (result) {
          if (!result.ok) {
            window.clearInterval(pollTimer);
            showError(result.data.error || "Lost track of this job.");
            progressPanel.hidden = true;
            return;
          }

          var job = result.data;

          if (!cueStripBuilt && job.total_chunks) {
            buildCueStrip(job.total_chunks);
          }
          updateCueStrip(job.completed_chunks, job.total_chunks);
          progressNote.textContent =
            job.completed_chunks + " of " + job.total_chunks + " chunks processed" +
            (job.failed_chunks ? " (" + job.failed_chunks + " need review)" : "");

          if (job.status === "done") {
            window.clearInterval(pollTimer);
            progressHeading.textContent = "Done";
            outputPanel.hidden = false;
            outputText.value = job.preview_text || "";
            failureBanner.hidden = !job.has_failures;
          } else if (job.status === "error") {
            window.clearInterval(pollTimer);
            showError(job.error || "Translation failed.");
            progressPanel.hidden = true;
          }
        })
        .catch(function () {
          // Transient network hiccup - keep polling rather than aborting.
        });
    }, 1200);
  }

  saveBtn.addEventListener("click", function () {
    if (!currentJobId) return;
    saveBtn.disabled = true;
    saveStatus.textContent = "Saving…";

    fetchJson("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJobId, text: outputText.value }),
    })
      .then(function (result) {
        if (!result.ok) {
          throw new Error(result.data.error || "Could not save.");
        }
        saveStatus.innerHTML =
          "Saved as " + result.data.filename + '. <a href="/files">View in Files</a>.';
      })
      .catch(function (err) {
        saveStatus.textContent = err.message;
      })
      .finally(function () {
        saveBtn.disabled = false;
      });
  });
})();
