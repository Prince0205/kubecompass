let yamlEditor = null
let currentYamlResource = null
let currentYamlName = null

window.openYamlEditor = async function (resource, name) {
  currentYamlResource = resource
  currentYamlName = name

  // include UI-selected context when fetching YAML
  const clusterSelect = document.getElementById("clusterSelect")
  const nsSelect = document.getElementById("namespaceSelect")
  const params = new URLSearchParams()
  if (clusterSelect && clusterSelect.value) params.set("cluster", clusterSelect.value)
  if (nsSelect && nsSelect.value) params.set("namespace", nsSelect.value)
  const query = params.toString() ? `?${params.toString()}` : ""

  const res = await fetch(`/api/resources/${resource}/${name}/yaml${query}`)
  if (!res.ok) {
    alert("Failed to load YAML")
    return
  }

  const data = await res.json()

  const html = `
    <div class="overlay-card">
      <h3>YAML: ${resource}/${name}</h3>

      <div id="yaml-editor" style="height: 450px;"></div>

      <div class="overlay-actions">
        <label style="display:flex;align-items:center;gap:8px;margin-right:auto">
          <input type="checkbox" id="dryRunCheckbox" /> <span>Dry run (preview)</span>
        </label>
        <button id="applyYamlBtn" onclick="applyYaml()">Apply</button>
        <button onclick="closeOverlay()">Cancel</button>
      </div>

      <div id="applyPreview" class="overlay-section" style="display:none;">
        <h4>Preview</h4>
        <div id="applyPreviewBox" class="log-box">Preview will appear here for dry-run</div>
      </div>
    </div>
  `

  openOverlay(`YAML: ${resource}/${name}`, html)

  require(["vs/editor/editor.main"], function () {
    if (yamlEditor) yamlEditor.dispose()

    yamlEditor = monaco.editor.create(
      document.getElementById("yaml-editor"),
      {
        value: data.yaml,
        language: "yaml",
        theme: "vs-dark",
        automaticLayout: true
      }
    )
    // update Apply button enabled state
    updateApplyButtonState()

    // listen for cluster/namespace selection changes to toggle Apply button
    const clusterSelect = document.getElementById("clusterSelect")
    const nsSelect = document.getElementById("namespaceSelect")
    if (clusterSelect) clusterSelect.addEventListener('change', updateApplyButtonState)
    if (nsSelect) nsSelect.addEventListener('change', updateApplyButtonState)
  })
}

async function applyYaml() {
  if (!yamlEditor) return;

  const yamlText = yamlEditor.getValue();
  // Include current UI context (cluster/namespace) so backend can resolve
  // which cluster to apply to when session isn't set. Require both values.
  const clusterSelect = document.getElementById("clusterSelect");
  const nsSelect = document.getElementById("namespaceSelect");
  const cluster = clusterSelect ? clusterSelect.value : null
  const namespace = nsSelect ? nsSelect.value : null
  const isDryRun = !!document.getElementById('dryRunCheckbox') && document.getElementById('dryRunCheckbox').checked

  if (!cluster || !namespace) {
    alert("Please select a cluster and namespace before applying YAML.");
    return;
  }

  // Confirm before applying changes (similar to kubectl edit confirmation)
  if (!isDryRun) {
    const confirmMsg = `Are you sure you want to apply changes to ${currentYamlResource}/${currentYamlName}?\n\nThis will modify the resource in the cluster.`;
    if (!confirm(confirmMsg)) {
      return;
    }
  }

  const payload = {
    yaml: yamlText,
    cluster,
    namespace,
    dry_run: isDryRun
  };

  // Show loading state
  const applyBtn = document.getElementById('applyYamlBtn')
  const originalBtnText = applyBtn ? applyBtn.textContent : 'Apply'
  if (applyBtn) {
    applyBtn.disabled = true
    applyBtn.textContent = 'Applying...'
  }

  try {
    const res = await fetch(
      `/api/resources/${currentYamlResource}/${currentYamlName}/yaml`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      }
    );

    if (!res.ok) {
      const errText = await res.text();
      let errorMessage = errText;
      try {
        const errJson = JSON.parse(errText);
        errorMessage = errJson.detail || errText;
      } catch (e) {}
      
      // Show error in preview area instead of alert for better UX
      document.getElementById('applyPreviewBox').textContent = `Error: ${errorMessage}`;
      document.getElementById('applyPreviewBox').classList.add('error');
      document.getElementById('applyPreview').style.display = 'block';
      
      // For validation errors (400), provide more specific feedback
      if (res.status === 400) {
        alert(`Validation Error: ${errorMessage}`);
      }
      return;
    }

    // If dry-run, show preview in overlay
    if (isDryRun) {
      let jsonBody = {}
      try {
        jsonBody = await res.json()
      } catch (e) {
        const txt = await res.text()
        document.getElementById('applyPreviewBox').textContent = txt
        document.getElementById('applyPreview').style.display = 'block'
        return
      }

      document.getElementById('applyPreviewBox').textContent = JSON.stringify(jsonBody.preview || jsonBody, null, 2)
      document.getElementById('applyPreviewBox').classList.remove('error');
      document.getElementById('applyPreview').style.display = 'block';
      alert("Dry run completed - see preview above. Click Apply again to confirm changes.");
      return
    }

    const result = await res.json();
    alert(result.message || "YAML applied successfully");
    closeYamlOverlay();
    
    // Trigger refresh of the resource list
    if (typeof window.refreshResourceList === 'function') {
      window.refreshResourceList(currentYamlResource);
    }
  } finally {
    if (applyBtn) {
      applyBtn.disabled = false
      applyBtn.textContent = originalBtnText
    }
  }
}

function updateApplyButtonState() {
  const btn = document.getElementById('applyYamlBtn')
  if (!btn) return
  const clusterSelect = document.getElementById("clusterSelect")
  const nsSelect = document.getElementById("namespaceSelect")
  const cluster = clusterSelect ? clusterSelect.value : null
  const namespace = nsSelect ? nsSelect.value : null
  btn.disabled = !(cluster && namespace)
}

function closeYamlOverlay() {
  document.getElementById("yaml-overlay").classList.add("hidden")
  document.getElementById("yaml-editor").innerHTML = ""
  if (yamlEditor) yamlEditor.dispose()
  yamlEditor = null
}