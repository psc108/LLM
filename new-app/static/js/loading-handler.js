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

    // Elements
    const overlay = document.getElementById('loading-overlay');
    const statusText = document.getElementById('loading-status');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');

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
            const response = await fetch('/api/model-status');
            if (!response.ok) throw new Error('Server error');

            const data = await response.json();

            if (data.actual_status === 'ok') {
                modelReady = true;
                updateStatus('Model ready!', 'starting application...');
                setTimeout(removeOverlay, 500);
                return;
            }

            // Handle downloading progress
            if (data.download_progress && data.download_progress.progress) {
                updateProgress(data.download_progress.progress);
            }

            // Continue checking if not ready
            if (!modelReady && !overlayRemoved) {
                setTimeout(checkModelStatus, 1000);
            }
        } catch (error) {
            console.error('Error checking model status:', error);
            updateStatus('Connection error', 'Application will start shortly...');
            // Continue checking anyway
            setTimeout(checkModelStatus, 2000);
        }
    }

    // Update status text
    function updateStatus(status, details) {
        if (statusText) {
            statusText.textContent = status;
        }

        const infoElement = document.getElementById('loading-info');
        if (infoElement && details) {
            infoElement.textContent = details;
        }
    }

    // Update progress bar
    function updateProgress(percent) {
        // Only update if increasing
        if (percent > progressPercentage) {
            progressPercentage = percent;

            if (progressBar) {
                progressBar.style.width = `${percent}%`;
            }

            if (progressText) {
                progressText.textContent = `${percent}% complete`;
            }

            // Update percentage display
            const percentageElement = document.getElementById('progress-percentage');
            if (percentageElement) {
                percentageElement.textContent = `${percent}%`;
            }

            // If 100%, prepare to remove overlay
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
