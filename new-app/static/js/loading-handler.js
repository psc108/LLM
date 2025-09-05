/**
 * Loading Overlay Handler
 * Provides better management of the loading overlay during app startup
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get loading timeout value from the server
    const loadingTimeoutValue = parseInt(window.LOADING_TIMEOUT || '20000');
    console.log(`Loading overlay timeout set to ${loadingTimeoutValue}ms`);

    // Variables to track state
    let modelReady = false;
    let overlayRemoved = false;
    let progressPercentage = 0;
    let progressCheckInterval;
    let modelDownloadAttempted = false;

    // Elements
    const overlay = document.getElementById('loading-overlay');
    const statusText = document.getElementById('loading-status');
    const infoText = document.getElementById('loading-info');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const spinner = document.getElementById('loading-spinner');
    const progressContainer = document.getElementById('progress-container');
    const progressPercentageEl = document.getElementById('progress-percentage');
    const currentFileEl = document.getElementById('current-file');
    const progressDetailsEl = document.getElementById('progress-details');

    // Check if model is ready immediately
    checkModelStatus();

    // Force remove overlay after timeout
    setTimeout(function() {
        if (!overlayRemoved) {
            console.log('Forcing removal of loading overlay after timeout');
            removeOverlay();
        }
    }, loadingTimeoutValue);

    // Function to check model status
    async function checkModelStatus() {
        try {
            // If model is ready or overlay is removed, stop checking
            if (modelReady || overlayRemoved) {
                return;
            }

            // Add cache-busting parameter for non-cached responses
            const timestamp = Date.now();
            const response = await fetch(`/api/model-status?_t=${timestamp}`);
            if (!response.ok) throw new Error('Server error');

            const data = await response.json();

            // Update UI based on status
            updateStatusIndicator(data);

            if (data.actual_status === 'ok') {
                modelReady = true;
                updateStatus('Model ready!', 'Starting application...');
                setTimeout(removeOverlay, 500);
                // Clear any intervals
                if (progressCheckInterval) {
                    clearInterval(progressCheckInterval);
                }
                return;
            }

            // Track polling count to diagnose issues
            window.modelStatusPolls = (window.modelStatusPolls || 0) + 1;
            console.log(`Model status poll #${window.modelStatusPolls}: ${data.actual_status}`);

            // Handle downloading progress
            if (data.actual_status === 'downloading' || 
                (data.download_progress && data.download_progress.downloading)) {
                // Show progress container, hide spinner
                if (progressContainer) progressContainer.style.display = 'block';
                if (spinner) spinner.style.display = 'none';

                // Update progress information
                if (data.download_progress) {
                    updateProgress(data.download_progress);
                    // Start tracking progress more frequently
                    startProgressTracking();
                }

                // Use a slower check interval during downloads
                if (!modelReady && !overlayRemoved) {
                    setTimeout(checkModelStatus, 3000); // Check every 3 seconds during download
                }
            } else if (data.actual_status === 'loading') {
                // Show spinner, hide progress container
                if (spinner) spinner.style.display = 'block';
                if (progressContainer) progressContainer.style.display = 'none';
                updateStatus('Initializing model...', 'This may take a moment...');

                // Try to trigger model download if not already attempted and status indicates loading
                // Only try to download if we're actually in loading status (not downloading or other states)
                if (!modelDownloadAttempted && data.model && data.actual_status === 'loading') {
                    console.log('Model needs to be downloaded, initiating download...');
                    modelDownloadAttempted = true;
                    initiateModelDownload(data.model);
                } else if (data.actual_status !== 'loading') {
                    console.log(`Not initiating download - status: ${data.actual_status}`);
                }

                // Continue checking if model is still loading
                if (!modelReady && !overlayRemoved) {
                    setTimeout(checkModelStatus, 5000); // Check every 5 seconds during loading (less frequent)
                }
            } else {
                // For other statuses (error, etc.), check less frequently
                if (!modelReady && !overlayRemoved) {
                    setTimeout(checkModelStatus, 5000); // Check every 5 seconds for other statuses
                }
            }
        } catch (error) {
            console.error('Error checking model status:', error);
            updateStatus('Connection error', 'Application will start shortly...');
            // Continue checking anyway but with increasing backoff
            const backoff = Math.min(10000, 3000 * Math.pow(1.5, window.modelStatusErrors || 0));
            window.modelStatusErrors = (window.modelStatusErrors || 0) + 1;
            console.log(`Connection error, retrying after ${backoff/1000} seconds (attempt ${window.modelStatusErrors})`);
            setTimeout(checkModelStatus, backoff);
        }
    }

    // Update status text
    function updateStatus(status, details) {
        if (statusText) {
            statusText.textContent = status;
        }

        if (infoText && details) {
            infoText.textContent = details;
        }
    }

    // Update status indicator in main UI
    function updateStatusIndicator(data) {
        const statusIndicator = document.getElementById('status-indicator');
        const statusTextEl = document.getElementById('status-text');
        const modelNameEl = document.getElementById('model-name');

        if (!statusIndicator || !statusTextEl) return;

        // Remove all status classes
        statusIndicator.className = 'status-indicator';

        // Update based on status
        if (data.actual_status === 'ok') {
            statusIndicator.classList.add('active');
            statusTextEl.textContent = 'Active';
        } else if (data.actual_status === 'downloading') {
            statusIndicator.classList.add('warning');
            statusTextEl.textContent = 'Downloading...';
        } else if (data.actual_status === 'loading') {
            statusIndicator.classList.add('warning');
            statusTextEl.textContent = 'Loading Model...';
        } else {
            statusIndicator.classList.add('error');
            statusTextEl.textContent = 'Error';
        }

        // Update model name if available
        if (modelNameEl && data.model) {
            modelNameEl.textContent = data.model;
        }
    }

    // Start progress tracking with more frequent updates
    function startProgressTracking() {
        // Clear existing interval if any
        if (progressCheckInterval) {
            clearInterval(progressCheckInterval);
            progressCheckInterval = null;
        }

        // Track consecutive errors to implement exponential backoff
        let consecutiveErrors = 0;

        // Set new interval for progress checking during download
        progressCheckInterval = setInterval(async function() {
            try {
                // Add cache buster to avoid cached responses
                const timestamp = Date.now();
                const response = await fetch(`/api/download-progress?_t=${timestamp}`);
                if (!response.ok) throw new Error(`Server error: ${response.status}`);

                const data = await response.json();
                updateProgress(data);

                // Reset error counter on success
                consecutiveErrors = 0;

                // If download is complete, stop tracking
                if (!data.downloading && data.progress >= 100) {
                    if (progressCheckInterval) {
                        clearInterval(progressCheckInterval);
                        progressCheckInterval = null;
                    }
                    updateStatus('Download complete!', 'Starting application...');
                    // Trigger a status check after a short delay
                    setTimeout(() => {
                        checkModelStatus();
                        // Schedule another check a bit later to ensure model is loaded
                        setTimeout(checkModelStatus, 5000);
                    }, 2000);
                }
            } catch (error) {
                console.error('Error fetching download progress:', error);

                // Implement exponential backoff for consecutive errors
                consecutiveErrors++;

                if (consecutiveErrors > 5) {
                    console.log('Too many consecutive errors, stopping progress tracking');
                    if (progressCheckInterval) {
                        clearInterval(progressCheckInterval);
                        progressCheckInterval = null;
                    }
                    // Try a model status check instead
                    setTimeout(checkModelStatus, 3000);
                }
            }
        }, 2000); // Check every 2 seconds instead of every 1 second
    }

    // Initiate model download
    async function initiateModelDownload(modelId) {
        try {
            // Check if we've already attempted to download this model in this session
            if (modelDownloadAttempted) {
                console.log(`Already attempted to download model: ${modelId}, not retrying`);
                return;
            }

            console.log(`Initiating download for model: ${modelId}`);
            updateStatus('Model not available', `Attempting to download ${modelId}...`);

            const response = await fetch('/api/download-model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ modelId: modelId })
            });

            const data = await response.json();
            console.log(`Download request response: ${response.status}`, data);

            if (response.status === 202) {
                // 202 Accepted - Download already in progress
                console.log('Download already in progress, tracking progress');
                startProgressTracking();
                updateStatus('Download in progress', `Downloading ${modelId}...`);

                // Mark as attempted to prevent redundant requests
                modelDownloadAttempted = true;
                return;
            }

            if (response.status === 429) {
                // 429 Too Many Requests - Rate limited
                const retryAfter = data.retry_after_seconds || 
                                  parseInt(response.headers.get('Retry-After') || '5', 10);

                console.log(`Rate limited. Retrying after ${retryAfter} seconds`);
                updateStatus('Download rate limited', `Will retry in ${retryAfter} seconds...`);

                // Schedule retry after the specified delay
                setTimeout(() => {
                    console.log('Retry timeout elapsed, attempting download again');
                    // Allow retry by resetting the attempt flag
                    modelDownloadAttempted = false;
                    initiateModelDownload(modelId);
                }, retryAfter * 1000);
                return;
            }

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            if (data.success) {
                // Start tracking progress
                startProgressTracking();
                updateStatus('Download started', `Downloading ${modelId}...`);

                // Mark as attempted to prevent redundant requests
                modelDownloadAttempted = true;
            }
        } catch (error) {
            console.error('Error initiating model download:', error);
            updateStatus('Download failed', 'Please check server logs');

            // Set a retry timer with exponential backoff if not rate limited response
            const backoffSeconds = 10;
            console.log(`Will retry download after ${backoffSeconds} seconds backoff`);

            setTimeout(() => {
                console.log('Backoff elapsed, attempting download again');
                modelDownloadAttempted = false;
                initiateModelDownload(modelId);
            }, backoffSeconds * 1000);
        }
    }

    // Update progress bar
    function updateProgress(progress) {
        // Get progress percentage (fallback to 0)
        const percent = progress.progress || 0;

        // Only update if increasing (prevents jumps backward)
        if (percent >= progressPercentage) {
            progressPercentage = percent;

            // Update progress bar
            if (progressBar) {
                progressBar.style.width = `${percent}%`;
            }

            // Update text elements
            if (progressText) {
                progressText.textContent = `${percent}% complete`;
            }

            if (progressPercentageEl) {
                progressPercentageEl.textContent = `${percent}%`;
            }

            // Update additional details if available
            if (currentFileEl && progress.file_name) {
                currentFileEl.textContent = `Current file: ${progress.file_name}`;
            }

            if (progressDetailsEl) {
                let details = [];
                if (progress.completed && progress.total) {
                    details.push(`${progress.completed} / ${progress.total}`);
                }
                if (progress.speed) {
                    details.push(progress.speed);
                }
                progressDetailsEl.textContent = details.join(' • ');
            }

            // If 100%, prepare to remove overlay after a delay
            if (percent >= 100) {
                updateStatus('Download complete!', 'Starting application...');
                setTimeout(checkModelStatus, 2000);
            }
        }
    }

    // Remove the overlay with animation
    function removeOverlay() {
        if (overlay && !overlayRemoved) {
            overlayRemoved = true;
            overlay.style.opacity = '0';
            setTimeout(function() {
                overlay.style.display = 'none';
            }, 500);
        }
    }
});
