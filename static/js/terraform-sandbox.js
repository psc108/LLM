/**
 * Terraform Sandbox UI JavaScript
 */

// Initialize the Terraform sandbox UI when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initTerraformUI();
});

// Global variables
let workspacesList = [];
let selectedWorkspace = null;
let resourceTypes = {};

/**
 * Initialize the Terraform sandbox UI
 */
function initTerraformUI() {
    // Add event listeners
    document.getElementById('create-workspace-btn')?.addEventListener('click', showCreateWorkspaceModal);
    document.getElementById('create-workspace-form')?.addEventListener('submit', createWorkspace);
    document.getElementById('refresh-workspaces-btn')?.addEventListener('click', loadWorkspaces);

    // Initialize the UI
    loadResourceTypes();
    loadWorkspaces();

    // Set up modal close buttons
    document.querySelectorAll('.modal .close-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            btn.closest('.modal').classList.remove('active');
        });
    });
}

/**
 * Load available AWS resource types
 */
async function loadResourceTypes() {
    try {
        const response = await fetch('/api/terraform/resource-types');
        if (!response.ok) {
            throw new Error('Failed to fetch resource types');
        }

        const data = await response.json();
        if (data.success) {
            resourceTypes = data.resource_types;
            renderResourceTypeHelp();
        } else {
            showError('Failed to load resource types: ' + data.error);
        }
    } catch (error) {
        console.error('Error loading resource types:', error);
        showError('Failed to load resource types: ' + error.message);
    }
}

/**
 * Render resource type help in the sidebar
 */
function renderResourceTypeHelp() {
    const container = document.getElementById('resource-types-list');
    if (!container) return;

    let html = '<h3>AWS Resources</h3>';
    html += '<ul class="resource-category-list">';

    for (const [category, resources] of Object.entries(resourceTypes)) {
        html += `
            <li>
                <div class="category-header" onclick="toggleCategory(this)">
                    <i class="fas fa-chevron-right"></i>
                    <span>${formatCategoryName(category)}</span>
                </div>
                <ul class="resource-list hidden">
        `;

        for (const [key, name] of Object.entries(resources)) {
            html += `
                <li>
                    <a href="#" onclick="showResourceHelp('${category}/${key}'); return false;">
                        <i class="fas fa-cube"></i> ${name}
                    </a>
                </li>
            `;
        }

        html += '</ul></li>';
    }

    html += '</ul>';
    container.innerHTML = html;
}

/**
 * Format a category name for display
 */
function formatCategoryName(category) {
    return category
        .replace(/_/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

/**
 * Toggle a resource category in the sidebar
 */
function toggleCategory(element) {
    const icon = element.querySelector('i');
    const resourceList = element.nextElementSibling;

    if (resourceList.classList.contains('hidden')) {
        resourceList.classList.remove('hidden');
        icon.classList.remove('fa-chevron-right');
        icon.classList.add('fa-chevron-down');
    } else {
        resourceList.classList.add('hidden');
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-right');
    }
}

/**
 * Show help for a specific resource type
 */
async function showResourceHelp(resourceType) {
    try {
        const response = await fetch(`/api/terraform/help/${resourceType}`);
        if (!response.ok) {
            throw new Error('Failed to fetch resource help');
        }

        const data = await response.json();
        if (data.success) {
            const helpData = data.help;
            const helpContainer = document.getElementById('resource-help-container');

            let html = `
                <h2>${formatCategoryName(helpData.resource_type)}</h2>
                <p>${helpData.description}</p>
            `;

            if (helpData.terraform_examples && helpData.terraform_examples.length > 0) {
                html += '<h3>Terraform Examples</h3>';
                helpData.terraform_examples.forEach(example => {
                    html += `<pre><code class="language-hcl">${escapeHtml(example)}</code></pre>`;
                });
            }

            if (helpData.documentation_links && helpData.documentation_links.length > 0) {
                html += '<h3>Documentation</h3><ul>';
                helpData.documentation_links.forEach(link => {
                    html += `<li><a href="${link.url}" target="_blank">${link.title}</a></li>`;
                });
                html += '</ul>';
            }

            helpContainer.innerHTML = html;

            // Initialize syntax highlighting if Prism is available
            if (typeof Prism !== 'undefined') {
                Prism.highlightAllUnder(helpContainer);
            }
        } else {
            showError('Failed to load resource help: ' + data.error);
        }
    } catch (error) {
        console.error('Error loading resource help:', error);
        showError('Failed to load resource help: ' + error.message);
    }
}

/**
 * Load all workspaces
 */
async function loadWorkspaces() {
    try {
        const response = await fetch('/api/terraform/workspaces');
        if (!response.ok) {
            throw new Error('Failed to fetch workspaces');
        }

        const data = await response.json();
        if (data.success) {
            workspacesList = data.workspaces;
            renderWorkspacesList();
        } else {
            showError('Failed to load workspaces: ' + data.error);
        }
    } catch (error) {
        console.error('Error loading workspaces:', error);
        showError('Failed to load workspaces: ' + error.message);
    }
}

/**
 * Render the workspaces list
 */
function renderWorkspacesList() {
    const container = document.getElementById('workspaces-list');
    if (!container) return;

    if (workspacesList.length === 0) {
        container.innerHTML = '<p>No workspaces found. Create a new workspace to get started.</p>';
        return;
    }

    let html = '<div class="workspaces-grid">';

    workspacesList.forEach(workspace => {
        const statusClass = getStatusClass(workspace.status);
        const createdDate = new Date(workspace.created_at).toLocaleString();

        html += `
            <div class="workspace-card" onclick="selectWorkspace('${workspace.workspace_id}')">
                <div class="workspace-header">
                    <span class="workspace-name">${workspace.config.project_name || workspace.workspace_id}</span>
                    <span class="workspace-status ${statusClass}">${workspace.status}</span>
                </div>
                <div class="workspace-body">
                    <p>ID: ${workspace.workspace_id}</p>
                    <p>Environment: ${workspace.config.environment || 'dev'}</p>
                    <p>Region: ${workspace.config.region || 'us-east-1'}</p>
                    <p>Created: ${createdDate}</p>
                </div>
                <div class="workspace-footer">
                    <button class="btn btn-sm" onclick="event.stopPropagation(); viewWorkspaceDetails('${workspace.workspace_id}')">
                        <i class="fas fa-info-circle"></i> Details
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); confirmDeleteWorkspace('${workspace.workspace_id}')">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

/**
 * Get the CSS class for a workspace status
 */
function getStatusClass(status) {
    switch (status) {
        case 'applied': return 'status-success';
        case 'initialized': return 'status-warning';
        default: return 'status-default';
    }
}

/**
 * Show the create workspace modal
 */
function showCreateWorkspaceModal() {
    // Reset the form
    const form = document.getElementById('create-workspace-form');
    if (form) form.reset();

    // Show the modal
    const modal = document.getElementById('create-workspace-modal');
    if (modal) modal.classList.add('active');
}

/**
 * Create a new workspace
 */
async function createWorkspace(event) {
    event.preventDefault();

    // Show loading state
    const submitButton = event.target.querySelector('button[type="submit"]');
    const originalText = submitButton.innerHTML;
    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
    submitButton.disabled = true;

    try {
        // Get form data
        const formData = new FormData(event.target);
        const data = Object.fromEntries(formData.entries());

        // Convert boolean values
        for (const key in data) {
            if (data[key] === 'true') data[key] = true;
            if (data[key] === 'false') data[key] = false;
        }

        // Send request to create workspace
        const response = await fetch('/terraform/workspaces', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            throw new Error(`Failed to create workspace: ${response.statusText}`);
        }

        const result = await response.json();
        if (result.success) {
            // Close the modal and reload workspaces
            const modal = document.getElementById('create-workspace-modal');
            if (modal) modal.classList.remove('active');

            showSuccess(`Workspace ${result.workspace_id} created successfully`);
            loadWorkspaces();

            // Select the new workspace
            setTimeout(() => {
                selectWorkspace(result.workspace_id);
            }, 1000);
        } else {
            showError('Failed to create workspace: ' + result.error);
        }
    } catch (error) {
        console.error('Error creating workspace:', error);
        showError('Failed to create workspace: ' + error.message);
    } finally {
        // Reset button state
        submitButton.innerHTML = originalText;
        submitButton.disabled = false;
    }
}

/**
 * Select a workspace and show its details
 */
async function selectWorkspace(workspaceId) {
    try {
        // Show loading state
        const container = document.getElementById('workspace-details-container');
        if (container) {
            container.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading workspace details...</div>';
        }

        const response = await fetch(`/api/terraform/workspaces/${workspaceId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch workspace details');
        }

        const data = await response.json();
        if (data.success) {
            selectedWorkspace = data.workspace;
            renderWorkspaceDetails();
        } else {
            showError('Failed to load workspace details: ' + data.error);
        }
    } catch (error) {
        console.error('Error selecting workspace:', error);
        showError('Failed to load workspace details: ' + error.message);
    }
}

/**
 * Render the details of the selected workspace
 */
function renderWorkspaceDetails() {
    if (!selectedWorkspace) return;

    const container = document.getElementById('workspace-details-container');
    if (!container) return;

    const workspace = selectedWorkspace;
    const statusClass = getStatusClass(workspace.status);

    let html = `
        <div class="workspace-header">
            <h2>${workspace.config.project_name || workspace.workspace_id}</h2>
            <span class="workspace-status ${statusClass}">${workspace.status}</span>
        </div>

        <div class="workspace-actions">
            <button class="btn btn-primary" onclick="planWorkspace('${workspace.workspace_id}')">
                <i class="fas fa-calculator"></i> Plan
            </button>
            <button class="btn btn-success" onclick="applyWorkspace('${workspace.workspace_id}')">
                <i class="fas fa-play"></i> Apply
            </button>
            <button class="btn btn-danger" onclick="confirmDestroyWorkspace('${workspace.workspace_id}')">
                <i class="fas fa-trash"></i> Destroy
            </button>
            <button class="btn" onclick="editWorkspaceVariables('${workspace.workspace_id}')">
                <i class="fas fa-edit"></i> Edit Variables
            </button>
        </div>

        <div class="workspace-details">
            <div class="details-section">
                <h3>Configuration</h3>
                <table class="details-table">
                    <tr>
                        <th>Workspace ID</th>
                        <td>${workspace.workspace_id}</td>
                    </tr>
                    <tr>
                        <th>Project Name</th>
                        <td>${workspace.config.project_name || 'Default'}</td>
                    </tr>
                    <tr>
                        <th>Environment</th>
                        <td>${workspace.config.environment || 'dev'}</td>
                    </tr>
                    <tr>
                        <th>Region</th>
                        <td>${workspace.config.region || 'us-east-1'}</td>
                    </tr>
                    <tr>
                        <th>Status</th>
                        <td><span class="${statusClass}">${workspace.status}</span></td>
                    </tr>
                    <tr>
                        <th>Created At</th>
                        <td>${new Date(workspace.created_at).toLocaleString()}</td>
                    </tr>
                </table>
            </div>
    `;

    // Resources section (if available)
    if (workspace.resources && workspace.resources.length > 0) {
        html += `
            <div class="details-section">
                <h3>Resources (${workspace.resources.length})</h3>
                <table class="details-table">
                    <thead>
                        <tr>
                            <th>Type</th>
                            <th>Name</th>
                            <th>Module</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        workspace.resources.forEach(resource => {
            html += `
                <tr>
                    <td>${resource.type}</td>
                    <td>${resource.name}</td>
                    <td>${resource.module || 'root'}</td>
                </tr>
            `;
        });

        html += '</tbody></table></div>';
    }

    // Outputs section (if available)
    if (workspace.outputs && Object.keys(workspace.outputs).length > 0) {
        html += `
            <div class="details-section">
                <h3>Outputs</h3>
                <div class="code-block">
                    <pre><code class="language-json">${JSON.stringify(workspace.outputs, null, 2)}</code></pre>
                </div>
            </div>
        `;
    }

    html += '</div>'; // Close workspace-details

    container.innerHTML = html;

    // Initialize syntax highlighting if Prism is available
    if (typeof Prism !== 'undefined') {
        Prism.highlightAllUnder(container);
    }
}

/**
 * Run Terraform plan on a workspace
 */
async function planWorkspace(workspaceId) {
    try {
        // Show loading message
        showInfo('Running terraform plan. This may take a few moments...');

        const response = await fetch(`/api/terraform/workspaces/${workspaceId}/plan`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`Failed to run plan: ${response.statusText}`);
        }

        const result = await response.json();

        if (result.success) {
            let message;
            if (result.plan_status === 'no_changes') {
                message = 'No changes. Your infrastructure matches the configuration.';
            } else if (result.plan_status === 'changes') {
                message = 'Plan succeeded. Changes detected.';
            } else {
                message = 'Plan completed.';
            }

            // Show plan output in a modal
            showOutputModal('Plan Results', message, result.plan_output);

            // Refresh workspace details
            selectWorkspace(workspaceId);
        } else {
            showError('Plan failed: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error running plan:', error);
        showError('Failed to run plan: ' + error.message);
    }
}

/**
 * Run Terraform apply on a workspace
 */
async function applyWorkspace(workspaceId) {
    if (!confirm('Are you sure you want to apply this configuration? This will create/modify resources in AWS.')) {
        return;
    }

    try {
        // Show loading message
        showInfo('Running terraform apply. This may take several minutes...');

        const response = await fetch(`/api/terraform/workspaces/${workspaceId}/apply`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`Failed to run apply: ${response.statusText}`);
        }

        const result = await response.json();

        if (result.success) {
            showSuccess('Apply succeeded! Resources have been created/updated.');

            // Show apply output in a modal
            showOutputModal('Apply Results', 'Apply completed successfully.', result.apply_output);

            // Refresh workspace details
            selectWorkspace(workspaceId);
        } else {
            showError('Apply failed: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error running apply:', error);
        showError('Failed to run apply: ' + error.message);
    }
}

/**
 * Confirm and run Terraform destroy on a workspace
 */
function confirmDestroyWorkspace(workspaceId) {
    if (confirm('Are you sure you want to destroy all resources in this workspace? This action cannot be undone.')) {
        destroyWorkspace(workspaceId);
    }
}

/**
 * Run Terraform destroy on a workspace
 */
async function destroyWorkspace(workspaceId) {
    try {
        // Show loading message
        showInfo('Running terraform destroy. This may take several minutes...');

        const response = await fetch(`/api/terraform/workspaces/${workspaceId}/destroy`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`Failed to run destroy: ${response.statusText}`);
        }

        const result = await response.json();

        if (result.success) {
            showSuccess('Destroy succeeded! All resources have been removed.');

            // Show destroy output in a modal
            showOutputModal('Destroy Results', 'Destroy completed successfully.', result.destroy_output);

            // Refresh workspace details and list
            loadWorkspaces();
            selectWorkspace(workspaceId);
        } else {
            showError('Destroy failed: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error running destroy:', error);
        showError('Failed to run destroy: ' + error.message);
    }
}

/**
 * Confirm and delete a workspace
 */
function confirmDeleteWorkspace(workspaceId) {
    if (confirm('Are you sure you want to delete this workspace? This will remove all Terraform files.\n\nNote: This will NOT destroy any deployed resources. Use the Destroy button first if you want to remove all resources.')) {
        deleteWorkspace(workspaceId);
    }
}

/**
 * Delete a workspace
 */
async function deleteWorkspace(workspaceId) {
    try {
        // Show loading message
        showInfo('Deleting workspace...');

        const response = await fetch(`/api/terraform/workspaces/${workspaceId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error(`Failed to delete workspace: ${response.statusText}`);
        }

        const result = await response.json();

        if (result.success) {
            showSuccess(`Workspace ${workspaceId} deleted successfully.`);

            // Refresh workspace list
            loadWorkspaces();

            // Clear selected workspace if it was deleted
            if (selectedWorkspace && selectedWorkspace.workspace_id === workspaceId) {
                selectedWorkspace = null;
                const container = document.getElementById('workspace-details-container');
                if (container) {
                    container.innerHTML = '<div class="empty-state">Select a workspace to view its details</div>';
                }
            }
        } else {
            showError('Delete failed: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error deleting workspace:', error);
        showError('Failed to delete workspace: ' + error.message);
    }
}

/**
 * Show a modal with output from a Terraform command
 */
function showOutputModal(title, message, output) {
    const outputModal = document.getElementById('output-modal');
    if (!outputModal) return;

    const modalTitle = outputModal.querySelector('.modal-title');
    const modalMessage = outputModal.querySelector('.modal-message');
    const outputContent = outputModal.querySelector('.output-content');

    if (modalTitle) modalTitle.textContent = title;
    if (modalMessage) modalMessage.textContent = message;
    if (outputContent) outputContent.textContent = output;

    outputModal.classList.add('active');
}

/**
 * Edit workspace variables
 */
function editWorkspaceVariables(workspaceId) {
    if (!selectedWorkspace) return;

    const variablesModal = document.getElementById('edit-variables-modal');
    if (!variablesModal) return;

    // Populate form with current values
    const form = variablesModal.querySelector('form');
    if (form) {
        // Clear existing fields
        const formFields = form.querySelector('#variable-fields');
        if (formFields) {
            formFields.innerHTML = '';

            // Add fields for each variable
            const config = selectedWorkspace.config || {};

            // Get all variable keys
            const keys = Object.keys(config).sort();

            // Create fields
            keys.forEach(key => {
                const value = config[key];
                const type = typeof value;

                let fieldHtml = `
                    <div class="form-group">
                        <label for="var-${key}">${formatVariableName(key)}</label>
                `;

                if (type === 'boolean') {
                    // Boolean toggle
                    fieldHtml += `
                        <select id="var-${key}" name="${key}">
                            <option value="true" ${value === true ? 'selected' : ''}>True</option>
                            <option value="false" ${value === false ? 'selected' : ''}>False</option>
                        </select>
                    `;
                } else if (key.includes('cidr')) {
                    // CIDR input
                    fieldHtml += `
                        <input type="text" id="var-${key}" name="${key}" value="${value}" placeholder="e.g., 10.0.0.0/16">
                    `;
                } else if (key === 'region') {
                    // Region dropdown
                    fieldHtml += `
                        <select id="var-${key}" name="${key}">
                            <option value="us-east-1" ${value === 'us-east-1' ? 'selected' : ''}>US East (N. Virginia)</option>
                            <option value="us-east-2" ${value === 'us-east-2' ? 'selected' : ''}>US East (Ohio)</option>
                            <option value="us-west-1" ${value === 'us-west-1' ? 'selected' : ''}>US West (N. California)</option>
                            <option value="us-west-2" ${value === 'us-west-2' ? 'selected' : ''}>US West (Oregon)</option>
                            <option value="eu-west-1" ${value === 'eu-west-1' ? 'selected' : ''}>EU (Ireland)</option>
                            <option value="eu-central-1" ${value === 'eu-central-1' ? 'selected' : ''}>EU (Frankfurt)</option>
                            <option value="ap-northeast-1" ${value === 'ap-northeast-1' ? 'selected' : ''}>Asia Pacific (Tokyo)</option>
                            <option value="ap-southeast-1" ${value === 'ap-southeast-1' ? 'selected' : ''}>Asia Pacific (Singapore)</option>
                        </select>
                    `;
                } else {
                    // Text input for other types
                    fieldHtml += `
                        <input type="text" id="var-${key}" name="${key}" value="${value}">
                    `;
                }

                fieldHtml += '</div>';
                formFields.innerHTML += fieldHtml;
            });

            // Set the form action
            form.setAttribute('data-workspace-id', workspaceId);

            // Set up form submission
            form.onsubmit = updateWorkspaceVariables;
        }
    }

    // Show the modal
    variablesModal.classList.add('active');
}

/**
 * Format a variable name for display
 */
function formatVariableName(variable) {
    return variable
        .replace(/_/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

/**
 * Update workspace variables
 */
async function updateWorkspaceVariables(event) {
    event.preventDefault();

    const form = event.target;
    const workspaceId = form.getAttribute('data-workspace-id');
/**
 * Terraform Sandbox JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    const configTextarea = document.getElementById('terraform-config');
    const analyzeBtn = document.getElementById('analyze-btn');
    const clearBtn = document.getElementById('clear-btn');
    const resultContainer = document.getElementById('analysis-result');

    // Auto-resize textarea
    configTextarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    // Analyze button click
    analyzeBtn.addEventListener('click', function() {
        const config = configTextarea.value.trim();
        if (!config) {
            showError('Please enter a Terraform configuration');
            return;
        }

        // Show loading state
        resultContainer.innerHTML = '<div class="loading">Analyzing your configuration...</div>';

        // Send to backend for analysis
        fetch('/api/analyze-terraform', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ config: config })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayAnalysisResults(data.results);
            } else {
                showError(data.error || 'An error occurred during analysis');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('Failed to analyze configuration. Please try again.');
        });
    });

    // Clear button click
    clearBtn.addEventListener('click', function() {
        configTextarea.value = '';
        resultContainer.innerHTML = '<p class="placeholder-text">Enter your Terraform configuration and click \'Analyze\' to see results</p>';
    });

    /**
     * Display analysis results
     */
    function displayAnalysisResults(results) {
        // Clear previous results
        resultContainer.innerHTML = '';

        if (!results || results.length === 0) {
            resultContainer.innerHTML = '<p class="info-text">No issues found in your configuration!</p>';
            return;
        }

        // Create results container
        const resultsDiv = document.createElement('div');
        resultsDiv.className = 'analysis-results';

        // Add each result
        results.forEach(result => {
            const resultItem = document.createElement('div');
            resultItem.className = `result-item ${result.severity}`;

            resultItem.innerHTML = `
                <div class="result-header">
                    <span class="severity-badge ${result.severity}">${result.severity}</span>
                    <h3>${result.title}</h3>
                </div>
                <p>${result.description}</p>
                ${result.recommendation ? `<div class="recommendation"><strong>Recommendation:</strong> ${result.recommendation}</div>` : ''}
            `;

            resultsDiv.appendChild(resultItem);
        });

        resultContainer.appendChild(resultsDiv);
    }

    /**
     * Show an error message
     */
    function showError(message) {
        resultContainer.innerHTML = `<div class="error-message"><i class="fas fa-exclamation-circle"></i> ${message}</div>`;
    }
});
    if (!workspaceId) {
        showError('Workspace ID not found');
        return;
    }

    // Show loading state
    const submitButton = form.querySelector('button[type="submit"]');
    const originalText = submitButton.innerHTML;
    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
    submitButton.disabled = true;

    try {
        // Get form data
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        // Convert boolean values
        for (const key in data) {
            if (data[key] === 'true') data[key] = true;
            if (data[key] === 'false') data[key] = false;
        }

        // Send request to update variables
        const response = await fetch(`/api/terraform/workspaces/${workspaceId}/variables`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            throw new Error(`Failed to update variables: ${response.statusText}`);
        }

        const result = await response.json();

        if (result.success) {
            // Close the modal
            const modal = document.getElementById('edit-variables-modal');
            if (modal) modal.classList.remove('active');

            showSuccess('Variables updated successfully');

            // Refresh workspace details
            selectWorkspace(workspaceId);
        } else {
            showError('Failed to update variables: ' + result.error);
        }
    } catch (error) {
        console.error('Error updating variables:', error);
        showError('Failed to update variables: ' + error.message);
    } finally {
        // Reset button state
        submitButton.innerHTML = originalText;
        submitButton.disabled = false;
    }
}

/**
 * Show a success message
 */
function showSuccess(message) {
    const notification = document.createElement('div');
    notification.className = 'notification success';
    notification.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
    showNotification(notification);
}

/**
 * Show an error message
 */
function showError(message) {
    const notification = document.createElement('div');
    notification.className = 'notification error';
    notification.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
    showNotification(notification);
}

/**
 * Show an info message
 */
function showInfo(message) {
    const notification = document.createElement('div');
    notification.className = 'notification info';
    notification.innerHTML = `<i class="fas fa-info-circle"></i> ${message}`;
    showNotification(notification);
}

/**
 * Show a notification
 */
function showNotification(notification) {
    const container = document.getElementById('notification-container');
    if (!container) return;

    container.appendChild(notification);

    // Remove after a delay
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => {
            container.removeChild(notification);
        }, 500);
    }, 5000);
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
