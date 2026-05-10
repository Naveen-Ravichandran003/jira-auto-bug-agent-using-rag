/**
 * Bug Pilot — Enterprise UI Application Logic
 * AI QA Copilot for Jira
 * ═══════════════════════════════════════════════════════
 */

const state = {
    currentStep: 1,
    connected: false,
    selectedFile: null,
    evidenceType: 'screenshot',
    generatedPayload: null,
    confidenceScore: 0,
    evidenceTrace: [],
    isGenerating: false,
    isSubmitting: false,
    isTestingConnection: false,
    evidenceFilePath: null,
};

const API_BASE = '';

const dom = {
    // Stepper
    stepItems: document.querySelectorAll('.step-item'),
    panels: {
        1: document.getElementById('panel-config'),
        2: document.getElementById('panel-evidence'),
        3: document.getElementById('panel-preview'),
    },
    stepMicrocopy: document.getElementById('step-microcopy'),

    // Config Panel
    baseUrl: document.getElementById('jira-base-url'),
    email: document.getElementById('jira-email'),
    apiToken: document.getElementById('jira-api-token'),
    groqApiKey: document.getElementById('groq-api-key'),
    projectKey: document.getElementById('jira-project-key'),
    llmModel: document.getElementById('llm-model'),
    customPrompt: document.getElementById('custom-prompt'),
    btnTestConnection: document.getElementById('btn-test-connection'),
    connectionResult: document.getElementById('connection-result'),
    connectionStatus: document.getElementById('connection-status'),
    connectionStatusDot: document.querySelector('#connection-status .status-dot'),
    connectionStatusText: document.querySelector('#connection-status .status-text'),

    // Sidebar
    sidebarInfoCard: document.getElementById('sidebar-info-card'),
    sidebarStaticContent: document.getElementById('sidebar-static-content'),
    sidebarDynamicContent: document.getElementById('sidebar-dynamic-content'),

    // Evidence Panel
    evidenceTypeOptions: document.querySelectorAll('.nav-opt'),
    uploadZone: document.getElementById('upload-zone'),
    fileInput: document.getElementById('evidence-file'),
    uploadedFile: document.getElementById('uploaded-file'),
    uploadedFilename: document.getElementById('uploaded-filename'),
    btnRemoveFile: document.getElementById('btn-remove-file'),
    jiraTicketInput: document.getElementById('jira-ticket-input'),
    existingTicketKey: document.getElementById('existing-ticket-key'),
    bugDescription: document.getElementById('bug-description'),
    btnGenerateBug: document.getElementById('btn-generate-bug'),

    // Preview Panel
    previewEmpty: document.getElementById('preview-empty'),
    previewLoading: document.getElementById('preview-loading'),
    previewContent: document.getElementById('preview-content'),
    previewSuccess: document.getElementById('preview-success'),
    confidenceValue: document.getElementById('confidence-value'),
    confidenceFill: document.getElementById('confidence-fill'),
    confidenceStatus: document.getElementById('confidence-status'),

    // Bug Editor
    editSummary: document.getElementById('edit-summary'),
    editDescription: document.getElementById('edit-description'),
    editSteps: document.getElementById('edit-steps'),
    editActual: document.getElementById('edit-actual'),
    editExpected: document.getElementById('edit-expected'),
    editPriority: document.getElementById('edit-priority'),
    traceChips: document.getElementById('trace-chips'),

    // Global Actions
    btnSubmitJira: document.getElementById('btn-submit-jira'),
    btnNewBug: document.getElementById('btn-new-bug'),
    successIssueKey: document.getElementById('success-issue-key'),
    successIssueLink: document.getElementById('success-issue-link'),

    // Footer Nav
    btnToStep2: document.getElementById('btn-to-step-2'),
    btnBackToStep1: document.getElementById('btn-back-to-step-1'),
    btnToStep3: document.getElementById('btn-to-step-3'),
    btnBackToStep2: document.getElementById('btn-back-to-step-2'),

    // Feedback
    toastContainer: document.getElementById('toast-container'),
};

const STEP_COPY = {
    1: 'Connect your Jira project and configure AI engine.',
    2: 'Add your bug evidence (screenshots, logs, or docs).',
    3: 'Review and file your structured bug report.'
};

// ═══════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    fetchConfig();
    updateGenerateButtonState();
});

function setupEventListeners() {
    // Wizard Navigation
    dom.btnToStep2?.addEventListener('click', () => goToStep(2));
    dom.btnBackToStep1?.addEventListener('click', () => {
        // Switch back to configuration step
        goToStep(1);
        updateSidebarForStep(1);
    });
    dom.btnToStep3?.addEventListener('click', () => goToStep(3));
    dom.btnBackToStep2?.addEventListener('click', () => {
        goToStep(2);
        updateSidebarForStep(2);
    });

    // Connection Test
    dom.btnTestConnection?.addEventListener('click', handleTestConnection);

    // Evidence Type Options
    dom.evidenceTypeOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            const type = opt.getAttribute('data-type');
            setEvidenceType(type);
        });
    });

    // File Handling
    dom.uploadZone?.addEventListener('click', () => dom.fileInput.click());
    dom.fileInput?.addEventListener('change', (e) => handleFileSelect(e.target.files[0]));
    dom.btnRemoveFile?.addEventListener('click', clearFile);

    // Drag and Drop
    dom.uploadZone?.addEventListener('dragenter', (e) => { e.preventDefault(); dom.uploadZone.style.borderColor = 'var(--brand-primary)'; });
    dom.uploadZone?.addEventListener('dragover', (e) => e.preventDefault());
    dom.uploadZone?.addEventListener('dragleave', (e) => { e.preventDefault(); dom.uploadZone.style.borderColor = 'var(--border-default)'; });
    dom.uploadZone?.addEventListener('drop', (e) => {
        e.preventDefault();
        dom.uploadZone.style.borderColor = 'var(--border-default)';
        handleFileSelect(e.dataTransfer.files[0]);
    });

    // Generation
    dom.btnGenerateBug?.addEventListener('click', handleGenerateBug);

    // Submission
    dom.btnSubmitJira?.addEventListener('click', handleSubmitToJira);

    // Reset
    dom.btnNewBug?.addEventListener('click', resetWizard);

    // Input monitoring for button state
    ['existing-ticket-key', 'bug-description'].forEach(id => {
        document.getElementById(id)?.addEventListener('input', updateGenerateButtonState);
    });
}

// ═══════════════════════════════════════════════════════
// WIZARD LOGIC
// ═══════════════════════════════════════════════════════
function goToStep(step) {
    state.currentStep = step;

    // Update Panes
    Object.keys(dom.panels).forEach(k => {
        dom.panels[k].style.display = k == step ? 'flex' : 'none';
        dom.panels[k].classList.toggle('active', k == step);
    });

    // Update Steps Progress
    dom.stepItems.forEach(item => {
        const itemStep = parseInt(item.getAttribute('data-step'));
        item.classList.remove('active', 'completed');
        if (itemStep === step) item.classList.add('active');
        if (itemStep < step) item.classList.add('completed');
    });

    // Update Microcopy
    if (dom.stepMicrocopy) {
        dom.stepMicrocopy.innerText = STEP_COPY[step] || '';
    }

    // Update Sidebar Context
    updateSidebarForStep(step);

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function updateSidebarForStep(step) {
    // If we're on step 1, show configuration summary if connected
    if (step === 1) {
        if (state.connected) {
            updateSidebarDynamicContent(`
                <div class="sidebar-conn-status">
                    <div class="sidebar-conn-badge">✅ Connected to Project</div>
                    <p class="sidebar-conn-msg">Mapping for project <strong>${dom.projectKey.value}</strong> active.</p>
                </div>
            `);
        } else {
            // Restore default Mock preview
            renderDefaultSidebarPreview('Waiting for Jira connection...');
        }
    } else if (step === 2) {
        // Step 2 Sidebar: Show Evidence status
        if (state.selectedFile || dom.bugDescription.value.length > 0) {
            updateSidebarDynamicContent(`
                <div class="info-preview-box">
                    <div class="preview-header">LIVE CONTEXT SCAN</div>
                    <div class="preview-mock">
                        <div class="mock-line" style="width: 80%; background: var(--brand-primary); opacity: 0.6;"></div>
                        <div class="mock-line" style="width: 60%; background: var(--brand-primary); opacity: 0.4;"></div>
                        <div class="mock-pill" style="background:var(--accent-emerald); color:white;">Evidence detected!</div>
                    </div>
                </div>
                <p class="sidebar-conn-msg" style="margin-top:1rem;">AI is ready to generate structured content from your input.</p>
            `);
        } else {
            renderDefaultSidebarPreview('Awaiting bug evidence...');
        }
    } else {
        // Step 3 Sidebar
        renderDefaultSidebarPreview('Reviewing analysis report.');
    }
}

function updateSidebarDynamicContent(html) {
    if (dom.sidebarDynamicContent) {
        dom.sidebarDynamicContent.innerHTML = html;
    }
}

function renderDefaultSidebarPreview(pillText) {
    updateSidebarDynamicContent(`
        <div class="info-preview-box">
            <div class="preview-header">LIVE PREVIEW</div>
            <div class="preview-mock">
                <div class="mock-line" style="width: 70%;"></div>
                <div class="mock-line" style="width: 40%;"></div>
                <div class="mock-pill">${pillText}</div>
            </div>
        </div>
    `);
}

function resetWizard() {
    state.generatedPayload = null;
    state.confidenceScore = 0;
    state.evidenceTrace = [];
    state.evidenceFilePath = null;
    state.selectedFile = null;

    dom.fileInput.value = '';
    dom.uploadedFile.style.display = 'none';
    dom.uploadZone.style.display = 'block';
    dom.bugDescription.value = '';
    dom.existingTicketKey.value = '';
    dom.btnToStep3.disabled = true;

    showPreviewState('empty');
    updateGenerateButtonState();
    goToStep(1);
    showToast('Resetting Bug Pilot for a new report', 'success');
}

// ═══════════════════════════════════════════════════════
// ACTION HANDLERS
// ═══════════════════════════════════════════════════════

async function handleTestConnection() {
    if (state.isTestingConnection) return;
    state.isTestingConnection = true;

    const btn = dom.btnTestConnection;
    const originalLabel = btn.querySelector('.btn-label').innerText;

    btn.classList.add('loading');
    btn.disabled = true;
    btn.querySelector('.btn-label').innerText = 'Validating Jira Access...';
    dom.connectionResult.style.display = 'none';

    const config = {
        base_url: dom.baseUrl.value.trim(),
        email: dom.email.value.trim(),
        api_token: dom.apiToken.value,
        project_key: dom.projectKey.value.trim(),
        groq_api_key: dom.groqApiKey.value.trim()
    };

    try {
        const response = await fetch(`${API_BASE}/api/test-connection`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        const data = await response.json();
        const alert = dom.connectionResult;
        alert.style.display = 'block';

        if (data.success) {
            state.connected = true;
            alert.className = 'connection-alert success';
            alert.innerText = `✓ Instance Verified: ${config.base_url}`;

            // Premium Button Interaction
            btn.classList.add('success-mode');
            btn.querySelector('.btn-label').innerText = '✅ Connected Successfully';

            updateConnectionBadge(true, config.project_key);
            updateSidebarForStep(1);
            showToast('Jira connection established!', 'success');
        } else {
            state.connected = false;
            alert.className = 'connection-alert error';
            alert.innerText = `✕ Error: ${data.message || 'Connection failed'}`;
            btn.classList.remove('success-mode');
            updateConnectionBadge(false);
            showToast('Verification failed. Check your tokens.', 'error');
        }
    } catch (e) {
        dom.connectionResult.style.display = 'block';
        dom.connectionResult.className = 'connection-alert error';
        dom.connectionResult.innerText = 'Network error while testing connection';
    } finally {
        state.isTestingConnection = false;
        btn.classList.remove('loading');
        btn.disabled = false;
        if (!state.connected) {
            btn.querySelector('.btn-label').innerText = originalLabel;
        }
    }
}

function updateConnectionBadge(isConnected, project = '') {
    if (isConnected) {
        dom.connectionStatusDot.className = 'status-dot connected';
        dom.connectionStatusText.innerHTML = `🟢 Connected: <strong>${project}</strong>`;
    } else {
        dom.connectionStatusDot.className = 'status-dot disconnected';
        dom.connectionStatusText.innerText = '🔴 Jira Not Connected';
    }
}

function setEvidenceType(type) {
    state.evidenceType = type;
    dom.evidenceTypeOptions.forEach(opt => opt.classList.toggle('active', opt.getAttribute('data-type') === type));

    // Toggle Inputs
    dom.uploadZone.style.display = (type === 'screenshot' || type === 'pdf') ? 'block' : 'none';
    dom.jiraTicketInput.style.display = (type === 'jira_ticket') ? 'block' : 'none';

    updateGenerateButtonState();
    updateSidebarForStep(state.currentStep);
}

function handleFileSelect(file) {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) return showToast('File too large (>10MB)', 'error');

    state.selectedFile = file;
    dom.uploadedFilename.innerText = file.name;
    dom.uploadedFile.style.display = 'flex';
    dom.uploadZone.style.display = 'none';
    updateGenerateButtonState();
    updateSidebarForStep(state.currentStep);
    showToast(`File attached: ${file.name}`, 'success');
}

function clearFile() {
    state.selectedFile = null;
    dom.fileInput.value = '';
    dom.uploadedFile.style.display = 'none';
    dom.uploadZone.style.display = 'block';
    updateGenerateButtonState();
    updateSidebarForStep(state.currentStep);
}

function updateGenerateButtonState() {
    let ready = false;
    if (state.evidenceType === 'screenshot' || state.evidenceType === 'pdf') {
        ready = !!state.selectedFile;
    } else if (state.evidenceType === 'jira_ticket') {
        ready = dom.existingTicketKey.value.trim().length > 0;
    } else {
        ready = dom.bugDescription.value.trim().length > 0;
    }
    dom.btnGenerateBug.disabled = !ready;

    // Auto-update sidebar if input added
    if (state.currentStep === 2) updateSidebarForStep(2);
}

async function handleGenerateBug() {
    if (state.isGenerating) return;

    goToStep(3);
    showPreviewState('loading');
    state.isGenerating = true;

    const formData = new FormData();
    formData.append('base_url', dom.baseUrl.value.trim());
    formData.append('email', dom.email.value.trim());
    formData.append('api_token', dom.apiToken.value);
    formData.append('project_key', dom.projectKey.value.trim());
    formData.append('groq_api_key', dom.groqApiKey.value.trim());
    formData.append('llm_model', dom.llmModel.value);
    formData.append('custom_prompt', dom.customPrompt.value);
    formData.append('evidence_type', state.evidenceType);
    formData.append('use_rag', 'true');
    formData.append('use_ai', 'true');

    if (state.selectedFile) formData.append('file', state.selectedFile);
    if (dom.bugDescription.value.trim()) formData.append('text_description', dom.bugDescription.value.trim());
    if (dom.existingTicketKey.value.trim()) formData.append('jira_ticket_key', dom.existingTicketKey.value.trim());

    try {
        const response = await fetch(`${API_BASE}/api/generate-bug`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (data.success) {
            state.generatedPayload = data.jira_ticket_payload;
            state.confidenceScore = data.confidence_score;
            state.evidenceTrace = data.evidence_trace || [];
            state.evidenceFilePath = data.evidence_file_path;

            populatePreview(data.jira_ticket_payload, data.confidence_score);
            showPreviewState('content');
            dom.btnToStep3.disabled = false;
            showToast('AI Synthesis Complete!', 'success');
        } else {
            showToast('Generation failed: ' + data.message, 'error');
            showPreviewState('empty');
        }
    } catch (e) {
        showToast('Generation error', 'error');
        showPreviewState('empty');
    } finally {
        state.isGenerating = false;
    }
}

function populatePreview(payload, confidence) {
    dom.editSummary.value = payload.summary;
    dom.editDescription.value = payload.description;
    dom.editSteps.value = payload.steps_to_reproduce || '';
    dom.editActual.value = payload.actual_result || '';
    dom.editExpected.value = payload.expected_result || '';

    if (payload.priority) {
        for (let opt of dom.editPriority.options) {
            if (opt.value.toLowerCase().includes(payload.priority.toLowerCase())) {
                opt.selected = true; break;
            }
        }
    }

    const cValue = Math.round(confidence * 100);
    dom.confidenceValue.innerText = `${cValue}%`;
    dom.confidenceFill.style.width = `${cValue}%`;

    let statusText = 'HIGH PRECISION';
    let color = 'var(--accent-emerald)';
    if (cValue < 80) { statusText = 'STANDARD PRECISION'; color = 'var(--accent-amber)'; }
    if (cValue < 50) { statusText = 'LOW PRECISION (NEEDS REVIEW)'; color = 'var(--accent-rose)'; }

    dom.confidenceStatus.innerText = statusText;
    dom.confidenceFill.style.background = color;
    dom.confidenceValue.style.color = color;

    dom.traceChips.innerHTML = state.evidenceTrace.map(t => `<span class="trace-chip">${t}</span>`).join('');
}

function showPreviewState(s) {
    dom.previewEmpty.style.display = s === 'empty' ? 'flex' : 'none';
    dom.previewLoading.style.display = s === 'loading' ? 'flex' : 'none';
    dom.previewContent.style.display = s === 'content' ? 'block' : 'none';
    dom.previewSuccess.style.display = s === 'success' ? 'flex' : 'none';
}

async function handleSubmitToJira() {
    if (state.isSubmitting) return;
    state.isSubmitting = true;

    const btn = dom.btnSubmitJira;
    const originalContent = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="modern-loader-mini"></span> Filing Jira Report...';

    const payload = {
        base_url: dom.baseUrl.value.trim(),
        email: dom.email.value.trim(),
        api_token: dom.apiToken.value,
        project_key: dom.projectKey.value.trim(),
        bug_payload: {
            summary: dom.editSummary.value,
            description: dom.editDescription.value,
            steps_to_reproduce: dom.editSteps.value,
            actual_result: dom.editActual.value,
            expected_result: dom.editExpected.value,
            priority: dom.editPriority.value
        },
        evidence_file_path: state.evidenceFilePath
    };

    try {
        const response = await fetch(`${API_BASE}/api/submit-bug`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (data.success) {
            dom.successIssueKey.innerText = data.issue_key;
            dom.successIssueLink.href = data.issue_url;
            showPreviewState('success');
            showToast('Bug Pilot successfully created ticket', 'success');
        } else {
            showToast('Jira submission failed', 'error');
        }
    } catch (e) {
        showToast('Submission error', 'error');
    } finally {
        state.isSubmitting = false;
        btn.disabled = false;
        btn.innerHTML = originalContent;
    }
}

async function fetchConfig() {
    try {
        const resp = await fetch(`${API_BASE}/api/config`);
        const data = await resp.json();
        if (data) {
            dom.baseUrl.value = data.base_url || '';
            dom.email.value = data.email || '';
            dom.projectKey.value = data.project_key || '';
            dom.groqApiKey.value = data.groq_api_key || '';
            if (data.base_url && data.project_key) {
                // Update header initially if cache exists
                updateConnectionBadge(false);
            }
        }
    } catch (e) { }
}

function showToast(msg, type = 'success') {
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerText = msg;
    dom.toastContainer.appendChild(t);
    setTimeout(() => {
        t.style.opacity = '0';
        setTimeout(() => t.remove(), 400);
    }, 4000);
}

window.togglePassword = (id) => {
    const el = document.getElementById(id);
    el.type = (el.type === 'password' ? 'text' : 'password');
};
