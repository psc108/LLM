/**
 * Terraform LLM Assistant - Main JavaScript
 * Enhanced version with improved message handling and UI interactions
 */

// Add CSS for loading text
const style = document.createElement('style');
style.textContent = `
    .loading-text {
        margin-top: 8px;
        font-size: 0.9em;
        color: #666;
        font-style: italic;
    }
`;
document.head.appendChild(style);

document.addEventListener('DOMContentLoaded', () => {
    console.log('App initializing...');

    // Let the loading-handler.js control the overlay

    // DOM Elements
    const chatMessages = document.getElementById('chat-messages');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const newChatButton = document.getElementById('new-chat-btn');
    const clearChatButton = document.getElementById('clear-chat-btn');
    const resetButton = document.getElementById('reset-button');
    const statusIndicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    const modelName = document.getElementById('model-name');
    const modelInfo = document.getElementById('model-info');

    // Initialize the application
    initializeApp();

    // Initialize app function
    function initializeApp() {
        // Auto-resize textarea
        if (messageInput) {
            messageInput.addEventListener('input', autoResizeTextarea);
        }

        // Event listeners
        if (sendButton) {
            sendButton.addEventListener('click', sendMessage);
        }

        if (messageInput) {
            messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }

        if (newChatButton) {
            newChatButton.addEventListener('click', resetChat);
        }

        if (clearChatButton) {
            clearChatButton.addEventListener('click', resetChat);
        }

        if (resetButton) {
            resetButton.addEventListener('click', resetChat);
        }

        // Check system status
        checkSystemStatus();

        // Set up periodic status checks
        setInterval(checkSystemStatus, 30000); // Every 30 seconds
    }

    // Auto-resize textarea
    function autoResizeTextarea() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 200) + 'px';
    }

    // Check system status
    function checkSystemStatus() {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                updateStatusUI(data);
            })
            .catch(error => {
                console.error('Health check failed:', error);
                updateStatusUI({ actual_status: 'error', error: 'Connection failed' });
            });
    }

    // Update status UI based on health check
    function updateStatusUI(data) {
        if (!statusIndicator || !statusText) return;

        // Update model name if available
        if (modelName && data.model) {
            modelName.textContent = data.model;
        }

        if (modelInfo && data.model) {
            modelInfo.textContent = data.model;
        }

        // Update status indicator
        statusIndicator.className = 'status-indicator';

        switch (data.actual_status) {
            case 'ok':
                statusIndicator.classList.add('active');
                statusText.textContent = 'Active';
                break;
            case 'downloading':
                statusIndicator.classList.add('warning');
                statusText.textContent = 'Downloading...';
                break;
            case 'loading':
                statusIndicator.classList.add('warning');
                statusText.textContent = 'Loading Model...';
                break;
            case 'error':
                statusIndicator.classList.add('error');
                statusText.textContent = 'Error';
                break;
            default:
                statusIndicator.classList.add('error');
                statusText.textContent = 'Unknown';
        }
    }

    // Send a message
    function sendMessage() {
        if (!messageInput || !chatMessages) return;

        const message = messageInput.value.trim();
        if (!message) return;

        // Clear input
        messageInput.value = '';
        messageInput.style.height = 'auto';
        messageInput.focus();

        // Add user message to chat
        addMessageToChat(message, 'user');

        // Disable input while processing
        if (messageInput) messageInput.disabled = true;
        if (sendButton) sendButton.disabled = true;

        // Add loading message
        const loadingMessage = addLoadingMessage();

        // Send to API with longer timeout handling
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minute timeout

        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message }),
            signal: controller.signal
        })
        .then(response => response.json())
        .then(data => {
            // Clear the timeout
            clearTimeout(timeoutId);

            // Remove loading message
            if (loadingMessage) {
                loadingMessage.remove();
            }

            // Add response
            if (data.success) {
                addMessageToChat(data.response, 'assistant');
            } else {
                addMessageToChat(`Error: ${data.error || 'Unknown error'}`, 'assistant');
            }
        })
        .catch(error => {
            // Clear the timeout
            clearTimeout(timeoutId);

            console.error('API error:', error);

            // Remove loading message
            if (loadingMessage) {
                loadingMessage.remove();
            }

            // Add appropriate error message
            if (error.name === 'AbortError') {
                addMessageToChat('The request took too long and was cancelled. The model may be busy or your question may be too complex. Please try again with a simpler query.', 'assistant');
            } else {
                addMessageToChat('Sorry, there was an error communicating with the server. Please try again.', 'assistant');
            }
        })
        .finally(() => {
            // Re-enable input
            if (messageInput) messageInput.disabled = false;
            if (sendButton) sendButton.disabled = false;
        });
    }

    // Add a message to the chat
    function addMessageToChat(content, sender) {
        if (!chatMessages) return;

        // Remove welcome screen if this is the first message
        const welcomeScreen = chatMessages.querySelector('.welcome-screen');
        if (welcomeScreen) {
            chatMessages.removeChild(welcomeScreen);
        }

        // Create message element
        const messageElement = document.createElement('div');
        messageElement.className = `message ${sender}`;

        // Create avatar
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';

        if (sender === 'assistant') {
            avatar.innerHTML = '<i class="fa-solid fa-robot"></i>';
        } else {
            avatar.innerHTML = '<i class="fa-solid fa-user"></i>';
        }

        // Format message content
        let formattedContent = content;

        // Format code blocks for assistant messages
        if (sender === 'assistant') {
            formattedContent = formatCodeBlocks(content);
        }

        // Create message content
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';

        // Create message bubble
        const messageBubble = document.createElement('div');
        messageBubble.className = 'message-bubble';
        messageBubble.innerHTML = formattedContent;

        // Create message timestamp
        const messageTime = document.createElement('div');
        messageTime.className = 'message-time';
        messageTime.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

        // Assemble message
        messageContent.appendChild(messageBubble);
        messageContent.appendChild(messageTime);

        messageElement.appendChild(avatar);
        messageElement.appendChild(messageContent);

        // Add to chat
        chatMessages.appendChild(messageElement);

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;

        return messageElement;
    }

    // Add a loading indicator message
    function addLoadingMessage() {
        if (!chatMessages) return null;

        // Remove welcome screen if this is the first message
        const welcomeScreen = chatMessages.querySelector('.welcome-screen');
        if (welcomeScreen) {
            chatMessages.removeChild(welcomeScreen);
        }

        // Create message element
        const messageElement = document.createElement('div');
        messageElement.className = 'message assistant';

        // Create avatar
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = '<i class="fa-solid fa-robot"></i>';

        // Create message content
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';

        // Create message bubble with typing indicator
        const messageBubble = document.createElement('div');
        messageBubble.className = 'message-bubble';
        messageBubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div><div class="loading-text">Generating response (this may take a while for complex questions)...</div>';

        // Assemble message
        messageContent.appendChild(messageBubble);

        messageElement.appendChild(avatar);
        messageElement.appendChild(messageContent);

        // Add to chat
        chatMessages.appendChild(messageElement);

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;

        return messageElement;
    }

    // Format code blocks in message content
    function formatCodeBlocks(content) {
        // First handle headers to make them more Confluence-like
        let formatted = content
            .replace(/^### (.*$)/gim, '<h3 style="color: #172B4D; font-size: 1.1rem; margin: 1rem 0 0.5rem;">$1</h3>') // h3
            .replace(/^## (.*$)/gim, '<h2 style="color: #172B4D; font-size: 1.25rem; margin: 1.25rem 0 0.5rem; padding-bottom: 0.3rem;">$1</h2>') // h2
            .replace(/^# (.*$)/gim, '<h1 style="color: #172B4D; font-size: 1.5rem; margin: 1.5rem 0 0.75rem; padding-bottom: 0.3rem;">$1</h1>') // h1

        // Handle lists to match Confluence style
        formatted = formatted
            .replace(/^\* (.*$)/gim, '<ul style="margin-left: 1.5rem; margin-bottom: 0.5rem;"><li>$1</li></ul>')
            .replace(/^\- (.*$)/gim, '<ul style="margin-left: 1.5rem; margin-bottom: 0.5rem;"><li>$1</li></ul>')
            .replace(/^\d+\. (.*$)/gim, '<ol style="margin-left: 1.5rem; margin-bottom: 0.5rem;"><li>$1</li></ol>')

            // Clean up repeated list tags
            .replace(/<\/ul>\s*<ul style="margin-left: 1\.5rem; margin-bottom: 0\.5rem;">/g, '')
            .replace(/<\/ol>\s*<ol style="margin-left: 1\.5rem; margin-bottom: 0\.5rem;">/g, '')

        // Handle code blocks with improved styling for Confluence look
        formatted = formatted.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, language, code) => {
            language = language || 'plaintext';
            // Format as Confluence-style code block
            return `
                <div style="margin: 0.75rem 0;">
                    <div style="font-size: 0.7rem; color: #6B778C; padding: 4px 8px; background-color: #F4F5F7; border: 1px solid #DFE1E6; border-bottom: none; border-radius: 3px 3px 0 0;">${language.trim() || 'code'}</div>
                    <pre style="margin-top: 0;"><code class="language-${language.trim()}">${code.trim()}</code></pre>
                </div>
            `;
        });

        // Format inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code style="background-color: #F4F5F7; padding: 2px 4px; border-radius: 3px; font-size: 0.85em; color: #172B4D;">$1</code>');

        // Handle paragraphs with appropriate spacing
        formatted = formatted.replace(/\n\n([^\n<].*)/g, '<p style="margin: 0.75rem 0; line-height: 1.5;">$1</p>');

        return formatted;
    }

// App is already initialized in the outer DOMContentLoaded event handler

// These functions are already defined elsewhere in the file
// and this is a duplicate implementation that's causing issues
}

// This function is already defined elsewhere in the file

// Add a message to the chat
function addMessage(type, content) {
    // Remove welcome screen if present
    const welcomeScreen = document.querySelector('.welcome-screen');
    if (welcomeScreen) {
        welcomeScreen.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message-container ${type}-message`;

    let avatar, name;
    if (type === 'user') {
        avatar = '<i class="fa-solid fa-user"></i>';
        name = 'You';
    } else if (type === 'ai') {
        avatar = '<i class="fa-solid fa-robot"></i>';
        name = 'AI Assistant';
    } else {
        avatar = '<i class="fa-solid fa-exclamation-triangle"></i>';
        name = 'System';
    }

    // Convert markdown in AI responses
    let formattedContent = content;
    if (type === 'ai') {
        // Format code blocks
        formattedContent = content.replace(/```(\w*)\n([\s\S]*?)\n```/g, function(match, language, code) {
            return `<div class="code-block">
                <div class="code-header">
                    <span class="code-language">${language || 'code'}</span>
                    <button class="btn btn-sm btn-link copy-code-btn" onclick="copyCode(this)">
                        <i class="fa-solid fa-copy"></i> Copy
                    </button>
                </div>
                <pre class="language-${language || 'plaintext'}"><code>${escapeHtml(code)}</code></pre>
            </div>`;
        });

        // Format inline code
        formattedContent = formattedContent.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Format headers
        formattedContent = formattedContent.replace(/^### (.*$)/gm, '<h3>$1</h3>');
        formattedContent = formattedContent.replace(/^## (.*$)/gm, '<h2>$1</h2>');
        formattedContent = formattedContent.replace(/^# (.*$)/gm, '<h1>$1</h1>');

        // Format bullet lists
        formattedContent = formattedContent.replace(/^\s*\*\s+(.*$)/gm, '<li>$1</li>');
        formattedContent = formattedContent.replace(/<\/li>\s*<li>/g, '</li><li>');
        formattedContent = formattedContent.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

        // Format paragraphs
        formattedContent = formattedContent.replace(/\n\n([^<].*?)\n\n/g, '<p>$1</p>');
    }

    messageDiv.innerHTML = `
        <div class="message-avatar">
            ${avatar}
        </div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-author">${name}</span>
                <span class="message-time">${formatTime(new Date())}</span>
            </div>
            <div class="message-text">${formattedContent}</div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Format time for messages
function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Escape HTML to prevent XSS
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Copy code to clipboard
function copyCode(button) {
    const codeBlock = button.closest('.code-block').querySelector('code');
    const textToCopy = codeBlock.textContent;

    navigator.clipboard.writeText(textToCopy).then(() => {
        // Change button text temporarily
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
        setTimeout(() => {
            button.innerHTML = originalText;
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy text: ', err);
    });
}

// Send example message
function sendExample(exampleText) {
    if (messageInput && exampleText) {
        messageInput.value = exampleText;
        sendMessage();
    }
}

// Check system status
function checkSystemStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            // Update status indicator
            if (data.status === 'ready') {
                statusIndicator.className = 'status-indicator status-ok';
                statusText.textContent = 'Ready';
            } else if (data.status === 'model_not_found') {
                statusIndicator.className = 'status-indicator status-warning';
                statusText.textContent = 'Loading Model';
            } else if (data.status === 'not_running') {
                statusIndicator.className = 'status-indicator status-error';
                statusText.textContent = 'Offline';
            } else {
                statusIndicator.className = 'status-indicator status-error';
                statusText.textContent = 'Error';
            }

            // Update model info
            if (data.model) {
                modelInfo.textContent = data.model;
                if (modelName) modelName.textContent = data.model;
            }

            // Hide loading overlay if it still exists
            const loadingOverlay = document.getElementById('loading-overlay');
            if (loadingOverlay) {
                loadingOverlay.style.opacity = '0';
                setTimeout(() => {
                    loadingOverlay.style.display = 'none';
                }, 300);
            }
        })
        .catch(error => {
            console.error('Error checking status:', error);
            statusIndicator.className = 'status-indicator status-error';
            statusText.textContent = 'Connection Error';

            // Hide loading overlay even on error
            const loadingOverlay = document.getElementById('loading-overlay');
            if (loadingOverlay) {
                loadingOverlay.style.opacity = '0';
                setTimeout(() => {
                    loadingOverlay.style.display = 'none';
                }, 300);
            }
        });
}

// Reset the chat (clear all messages)
function resetChat() {
    // Clear all existing messages
    chatMessages.innerHTML = '';

    // Add welcome screen back
    chatMessages.innerHTML = `
        <div class="welcome-screen">
            <div class="welcome-header">
                <h2>Welcome to ${document.title}</h2>
                <p>Your AI companion for infrastructure and cloud architecture</p>
            </div>

            <div class="examples-grid">
                <div class="example-card" onclick="sendExample('Create an S3 bucket with versioning and encryption')">
                    <div class="example-icon"><i class="fa-solid fa-cube"></i></div>
                    <div class="example-content">
                        <h3>S3 Storage</h3>
                        <p>Create an S3 bucket with versioning and encryption</p>
                        <span class="lozenge lozenge-blue">AWS</span>
                    </div>
                </div>

                <div class="example-card" onclick="sendExample('Set up a VPC with public and private subnets')">
                    <div class="example-icon"><i class="fa-solid fa-network-wired"></i></div>
                    <div class="example-content">
                        <h3>Networking</h3>
                        <p>Set up a VPC with public and private subnets</p>
                        <span class="lozenge lozenge-purple">Terraform</span>
                    </div>
                </div>

                <div class="example-card" onclick="sendExample('Deploy EC2 instances with autoscaling')">
                    <div class="example-icon"><i class="fa-solid fa-server"></i></div>
                    <div class="example-content">
                        <h3>Compute</h3>
                        <p>Deploy EC2 instances with autoscaling</p>
                        <span class="lozenge lozenge-green">DevOps</span>
                    </div>
                </div>

                <div class="example-card" onclick="sendExample('Create an RDS database with backups and security')">
                    <div class="example-icon"><i class="fa-solid fa-database"></i></div>
                    <div class="example-content">
                        <h3>Database</h3>
                        <p>Create an RDS database with backups and security</p>
                        <span class="lozenge lozenge-yellow">Security</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function initializeApp() {
    // Auto-resize textarea
    if (messageInput) {
        messageInput.addEventListener('input', autoResizeTextarea);
    }

    // Event listeners
    if (sendButton) {
        sendButton.addEventListener('click', sendMessage);
    }

    if (messageInput) {
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    if (newChatButton) {
        newChatButton.addEventListener('click', resetChat);
    }

    if (clearChatButton) {
        clearChatButton.addEventListener('click', resetChat);
    }

    if (resetButton) {
        resetButton.addEventListener('click', resetChat);
    }

    // Check system status
    checkSystemStatus();

    // Set up periodic status checks
    setInterval(checkSystemStatus, 30000); // Every 30 seconds
}
        // Assemble message
        messageContent.appendChild(messageBubble);
        messageContent.appendChild(messageTime);

        messageElement.appendChild(avatar);
        messageElement.appendChild(messageContent);

        // Add to chat
        chatMessages.appendChild(messageElement);

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;

        return messageElement;
    }

    // Add a loading indicator message
    function addLoadingMessage() {
        if (!chatMessages) return null;

        // Remove welcome screen if this is the first message
        const welcomeScreen = chatMessages.querySelector('.welcome-screen');
        if (welcomeScreen) {
            chatMessages.removeChild(welcomeScreen);
        }

        // Create message element
        const messageElement = document.createElement('div');
        messageElement.className = 'message assistant';

        // Create avatar
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = '<i class="fa-solid fa-robot"></i>';

        // Create message content
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';

        // Create message bubble with typing indicator
        const messageBubble = document.createElement('div');
        messageBubble.className = 'message-bubble';
        messageBubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div><div class="loading-text">Generating response (this may take a while for complex questions)...</div>';

        // Assemble message
        messageContent.appendChild(messageBubble);

        messageElement.appendChild(avatar);
        messageElement.appendChild(messageContent);

        // Add to chat
        chatMessages.appendChild(messageElement);

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;

        return messageElement;
    }

    // Format code blocks in message content - Enhanced for Confluence style
    function formatCodeBlocks(content) {
        // First handle headers to make them more Confluence-like
        let formatted = content
            .replace(/^### (.*$)/gim, '<h3 style="color: #172B4D; font-size: 1.1rem; margin: 1rem 0 0.5rem;">$1</h3>') // h3
            .replace(/^## (.*$)/gim, '<h2 style="color: #172B4D; font-size: 1.25rem; margin: 1.25rem 0 0.5rem; padding-bottom: 0.3rem;">$1</h2>') // h2
            .replace(/^# (.*$)/gim, '<h1 style="color: #172B4D; font-size: 1.5rem; margin: 1.5rem 0 0.75rem; padding-bottom: 0.3rem;">$1</h1>') // h1

        // Handle lists to match Confluence style
        formatted = formatted
            .replace(/^\* (.*$)/gim, '<ul style="margin-left: 1.5rem; margin-bottom: 0.5rem;"><li>$1</li></ul>')
            .replace(/^\- (.*$)/gim, '<ul style="margin-left: 1.5rem; margin-bottom: 0.5rem;"><li>$1</li></ul>')
            .replace(/^\d+\. (.*$)/gim, '<ol style="margin-left: 1.5rem; margin-bottom: 0.5rem;"><li>$1</li></ol>')

            // Clean up repeated list tags
            .replace(/<\/ul>\s*<ul style="margin-left: 1\.5rem; margin-bottom: 0\.5rem;">/g, '')
            .replace(/<\/ol>\s*<ol style="margin-left: 1\.5rem; margin-bottom: 0\.5rem;">/g, '')

        // Handle code blocks with improved styling for Confluence look
        formatted = formatted.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, language, code) => {
            language = language || 'plaintext';
            // Format as Confluence-style code block
            return `
                <div style="margin: 0.75rem 0;">
                    <div style="font-size: 0.7rem; color: #6B778C; padding: 4px 8px; background-color: #F4F5F7; border: 1px solid #DFE1E6; border-bottom: none; border-radius: 3px 3px 0 0;">${language.trim() || 'code'}</div>
                    <pre style="margin-top: 0;"><code class="language-${language.trim()}">${code.trim()}</code></pre>
                </div>
            `;
        });

        // Format inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code style="background-color: #F4F5F7; padding: 2px 4px; border-radius: 3px; font-size: 0.85em; color: #172B4D;">$1</code>');

        // Handle paragraphs with appropriate spacing
        formatted = formatted.replace(/\n\n([^\n<].*)/g, '<p style="margin: 0.75rem 0; line-height: 1.5;">$1</p>');

        return formatted;
    }

    // Reset chat - clear all messages and show welcome screen
    function resetChat() {
        if (!chatMessages) return;

        // Clear all messages
        chatMessages.innerHTML = `
            <div class="welcome-screen">
                <div class="welcome-header">
                    <h2>Welcome to Terraform LLM Assistant</h2>
                    <p>Your AI companion for infrastructure and cloud architecture</p>
                </div>

                <div class="examples-grid">
                    <div class="example-card" onclick="sendExample('Create an S3 bucket with versioning and encryption')">
                        <div class="example-icon"><i class="fa-solid fa-cube"></i></div>
                        <div class="example-content">
                            <h3>S3 Storage</h3>
                            <p>Create an S3 bucket with versioning and encryption</p>
                            <span class="lozenge lozenge-blue">AWS</span>
                        </div>
                    </div>

                    <div class="example-card" onclick="sendExample('Set up a VPC with public and private subnets')">
                        <div class="example-icon"><i class="fa-solid fa-network-wired"></i></div>
                        <div class="example-content">
                            <h3>Networking</h3>
                            <p>Set up a VPC with public and private subnets</p>
                            <span class="lozenge lozenge-purple">Terraform</span>
                        </div>
                    </div>

                    <div class="example-card" onclick="sendExample('Deploy EC2 instances with autoscaling')">
                        <div class="example-icon"><i class="fa-solid fa-server"></i></div>
                        <div class="example-content">
                            <h3>Compute</h3>
                            <p>Deploy EC2 instances with autoscaling</p>
                            <span class="lozenge lozenge-green">DevOps</span>
                        </div>
                    </div>

                    <div class="example-card" onclick="sendExample('Create an RDS database with backups and security')">
                        <div class="example-icon"><i class="fa-solid fa-database"></i></div>
                        <div class="example-content">
                            <h3>Database</h3>
                            <p>Create an RDS database with backups and security</p>
                            <span class="lozenge lozenge-yellow">Security</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // Global function to send example prompts
    window.sendExample = function(text) {
        if (!messageInput) return;

        messageInput.value = text;

        // Trigger auto-resize
        messageInput.dispatchEvent(new Event('input'));

        // Send the message
        sendMessage();
    };

    // This resetChat function is already defined elsewhere in the file
document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const chatMessages = document.getElementById('chat-messages');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const clearChatBtn = document.getElementById('clear-chat-btn');
    const newChatBtn = document.getElementById('new-chat-btn') || document.getElementById('reset-button');
    const statusIndicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    const loadingOverlay = document.getElementById('loading-overlay');

    // Auto-resize text area
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    // Check LLM status on load
    checkStatus();

    // Hide loading overlay once everything is loaded
    if (loadingOverlay) {
        setTimeout(() => {
            loadingOverlay.style.opacity = '0';
            setTimeout(() => loadingOverlay.style.display = 'none', 300);
        }, 1000);
    }

    // Initialize chat
    initChat();

    // Event listeners
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', clearChat);
    }

    if (newChatBtn) {
        newChatBtn.addEventListener('click', startNewChat);
    }

    // Send example message when clicked
    window.sendExample = function(text) {
        // Remove welcome screen
        const welcomeScreen = document.querySelector('.welcome-screen');
        if (welcomeScreen) {
            welcomeScreen.style.display = 'none';
        }

        // Set the input value and send
        messageInput.value = text;
        sendMessage();
    };

    // Functions
    function checkStatus() {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ready') {
                    statusIndicator.classList.add('status-active');
                    statusText.textContent = 'Ready';
                } else if (data.status === 'not_running') {
                    statusIndicator.classList.add('status-error');
                    statusText.textContent = 'Ollama Not Running';
                } else if (data.status === 'model_not_found') {
                    statusIndicator.classList.add('status-warning');
                    statusText.textContent = 'Model Not Found';
                } else {
                    statusIndicator.classList.add('status-error');
                    statusText.textContent = 'Error';
                }
            })
            .catch(error => {
                console.error('Error checking status:', error);
                statusIndicator.classList.add('status-error');
                statusText.textContent = 'Connection Error';
            });
    }

    function initChat() {
        // Check if there are saved messages
        const savedMessages = localStorage.getItem('chatMessages');
        if (savedMessages) {
            // If we have saved messages, hide the welcome screen
            const welcomeScreen = document.querySelector('.welcome-screen');
            if (welcomeScreen) {
                welcomeScreen.style.display = 'none';
            }

            // Display saved messages
            chatMessages.innerHTML = savedMessages;
            scrollToBottom();
        }
    }

    function sendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;

        // Remove welcome screen if present
        const welcomeScreen = document.querySelector('.welcome-screen');
        if (welcomeScreen) {
            welcomeScreen.style.display = 'none';
        }

        // Add user message to chat
        addMessageToChat('user', message);

        // Clear input and reset height
        messageInput.value = '';
        messageInput.style.height = 'auto';

        // Add loading message
        const loadingId = 'loading-' + Date.now();
        addLoadingMessage(loadingId);

        // Send message to backend
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message }),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Remove loading message
            const loadingMessage = document.getElementById(loadingId);
            if (loadingMessage) {
                loadingMessage.remove();
            }

            // Add AI response
            addMessageToChat('assistant', data.response);

            // Save conversation to localStorage
            localStorage.setItem('chatMessages', chatMessages.innerHTML);
        })
        .catch(error => {
            console.error('Error:', error);

            // Remove loading message
            const loadingMessage = document.getElementById(loadingId);
            if (loadingMessage) {
                loadingMessage.remove();
            }

            // Add error message
            addMessageToChat('error', `Error: ${error.message || 'Failed to connect to the server. Please try again.'}`);

            // Save conversation to localStorage
            localStorage.setItem('chatMessages', chatMessages.innerHTML);
        });
    }

    function addMessageToChat(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;

        const iconClass = role === 'user' ? 'fa-user' : 
                        role === 'assistant' ? 'fa-robot' : 'fa-exclamation-triangle';

        // Create message with proper markup
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas ${iconClass}"></i>
            </div>
            <div class="message-content">
                <div class="message-text">${formatMessage(content)}</div>
                <div class="message-time">${getCurrentTime()}</div>
            </div>
        `;

        chatMessages.appendChild(messageDiv);
        scrollToBottom();

        // Add syntax highlighting if needed
        if (window.hljs) {
            messageDiv.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightBlock(block);
            });
        }
    }

    function addLoadingMessage(id) {
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message assistant-message';
        loadingDiv.id = id;

        loadingDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="message-text">
                    <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            </div>
        `;

        chatMessages.appendChild(loadingDiv);
        scrollToBottom();
    }

    function formatMessage(message) {
        // First, escape HTML to prevent XSS
        const escapeHtml = (unsafe) => {
            return unsafe
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        };

        const escaped = escapeHtml(message);

        // Process code blocks with triple backticks with language
        let formatted = escaped.replace(/```([a-z]*)(\n|\s)(([\s\S](?!```))*?)```/gm, function(match, language, newline, code) {
            return `<pre><code class="language-${language || 'plaintext'}">${code}</code></pre>`;
        });

        // Process inline code with single backtick
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Convert line breaks to <br>
        formatted = formatted.replace(/\n/g, '<br>');

        return formatted;
    }

    function getCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function clearChat() {
        // Confirm before clearing
        if (confirm('Are you sure you want to clear the chat history?')) {
            localStorage.removeItem('chatMessages');

            // Reload page to show welcome screen
            window.location.reload();
        }
    }

    function startNewChat() {
        // Start a new chat (similar to clear but without confirmation)
        localStorage.removeItem('chatMessages');
        window.location.reload();
    }
});
                    <div class="example-card" onclick="sendExample('Deploy EC2 instances with autoscaling')">
                        <div class="example-icon"><i class="fa-solid fa-server"></i></div>
                        <div class="example-content">
                            <h3>Compute</h3>
                            <p>Deploy EC2 instances with autoscaling</p>
                        </div>
                    </div>
// App initialization
let chatHistory = [];
let statusCheckInterval;
let progressCheckInterval;
let modelReady = false;

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Start checking model status
    checkModelStatus();

    // Set up event listeners
    setupEventListeners();

    // Set up periodic status checks
    statusCheckInterval = setInterval(checkModelStatus, 5000);
});

// Set up event listeners for UI elements
function setupEventListeners() {
    // Send button click
    const sendButton = document.getElementById('send-button');
    if (sendButton) {
        sendButton.addEventListener('click', sendMessage);
    }

    // Message input enter key
    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    // Reset button
    const resetButton = document.getElementById('reset-button');
    if (resetButton) {
        resetButton.addEventListener('click', resetConversation);
    }

    // Clear chat button
    const clearChatBtn = document.getElementById('clear-chat-btn');
    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', resetConversation);
    }

    // New chat button
    const newChatBtn = document.getElementById('new-chat-btn');
    if (newChatBtn) {
        newChatBtn.addEventListener('click', resetConversation);
    }
}

// Check model status
async function checkModelStatus() {
    try {
        const response = await fetch('/api/model-status');
        const data = await response.json();

        // Update status indicators
        updateStatusIndicators(data);

        // Handle loading overlay
        handleLoadingOverlay(data);

        // Handle different statuses
        if (data.actual_status === 'ok' && !modelReady) {
            // Model just became ready
            modelReady = true;
            hideLoadingOverlay();
            welcomeUser();

            // Stop frequent checking
            clearInterval(progressCheckInterval);
            // Switch to less frequent checks
            clearInterval(statusCheckInterval);
            statusCheckInterval = setInterval(checkModelStatus, 30000);
        } else if (data.actual_status === 'downloading') {
            // Model is downloading
            startProgressTracking();
        } else if (data.actual_status === 'loading' && !data.download_progress.downloading) {
            // Try to download the model if it's not downloading already
            triggerModelDownload(data.model);
        }
    } catch (error) {
        console.error('Error checking model status:', error);
    }
}

// Update status indicators in the UI
function updateStatusIndicators(data) {
    const statusIndicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    const modelName = document.getElementById('model-name');
    const modelInfo = document.getElementById('model-info');

    if (statusIndicator && statusText) {
        // Reset all status classes
        statusIndicator.className = 'status-indicator';

        // Update based on status
        if (data.actual_status === 'ok') {
            statusIndicator.classList.add('status-ok');
            statusText.textContent = 'Ready';
        } else if (data.actual_status === 'downloading') {
            statusIndicator.classList.add('status-downloading');
            statusText.textContent = 'Downloading...';
        } else if (data.actual_status === 'loading') {
            statusIndicator.classList.add('status-loading');
            statusText.textContent = 'Loading...';
        } else {
            statusIndicator.classList.add('status-error');
            statusText.textContent = 'Error';
        }

        // Update model name if provided
        if (modelName && data.model) {
            modelName.textContent = data.model;
        }

        if (modelInfo && data.model) {
            modelInfo.textContent = data.model;
        }
    }
}

// Handle loading overlay based on model status
function handleLoadingOverlay(data) {
    const overlay = document.getElementById('loading-overlay');
    const progressContainer = document.getElementById('progress-container');
    const spinner = document.getElementById('loading-spinner');
    const loadingStatus = document.getElementById('loading-status');
    const loadingInfo = document.getElementById('loading-info');

    if (!overlay) return;

    // Update overlay based on status
    if (data.actual_status === 'ok') {
        // If model is ready, hide overlay
        if (progressContainer) progressContainer.style.display = 'none';
        if (spinner) spinner.style.display = 'none';
        if (loadingStatus) loadingStatus.textContent = 'Ready!';
        if (loadingInfo) loadingInfo.textContent = 'Starting application...';

        // Hide with delay
        setTimeout(() => {
            overlay.style.opacity = '0';
            setTimeout(() => {
                overlay.style.display = 'none';
            }, 300);
        }, 500);
    } else if (data.actual_status === 'downloading') {
        // Show progress for downloading
        if (progressContainer) progressContainer.style.display = 'block';
        if (spinner) spinner.style.display = 'none';
        if (loadingStatus) loadingStatus.textContent = 'Downloading model...';
        if (data.download_progress) {
            updateProgressBar(data.download_progress);
        }
    } else if (data.actual_status === 'loading') {
        // Show spinner for loading
        if (progressContainer) progressContainer.style.display = 'none';
        if (spinner) spinner.style.display = 'block';
        if (loadingStatus) loadingStatus.textContent = 'Initializing model...';
        if (loadingInfo) loadingInfo.textContent = 'This may take a moment...';
    } else {
        // Error state
        if (progressContainer) progressContainer.style.display = 'none';
        if (spinner) spinner.style.display = 'block';
        if (loadingStatus) loadingStatus.textContent = 'Service unavailable';
        if (loadingInfo) loadingInfo.textContent = 'Please check that Ollama is installed and running';
    }
}

// Update progress bar during model download
function updateProgressBar(progress) {
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const progressPercentage = document.getElementById('progress-percentage');
    const progressDetails = document.getElementById('progress-details');

    if (progressBar && progressPercentage && progressText) {
        // Store the last progress to prevent jumping backwards
        if (!window.lastProgress) window.lastProgress = 0;

        // Only update if progress increases
        const newProgress = progress.progress || 0;
        if (newProgress >= window.lastProgress) {
            // Update progress bar with smooth animation
            progressBar.style.width = newProgress + '%';
            window.lastProgress = newProgress;

            // Update text elements
            progressPercentage.textContent = `${newProgress}%`;
            progressText.textContent = progress.status || 'Downloading...';

            // Update details if available
            if (progressDetails) {
                let details = [];
                if (progress.completed && progress.total) {
                    details.push(`${progress.completed} / ${progress.total}`);
                }
                if (progress.speed) {
                    details.push(progress.speed);
                }
                progressDetails.textContent = details.join(' • ');
            }
        }
    }
}

// Start frequent progress tracking during download
function startProgressTracking() {
    // Clear existing interval if any
    if (progressCheckInterval) {
        clearInterval(progressCheckInterval);
    }

    // Check progress more frequently during download
    progressCheckInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/download-progress');
            const data = await response.json();
            updateProgressBar(data);

            // If download complete, stop checking
            if (!data.downloading && data.progress >= 100) {
                clearInterval(progressCheckInterval);
                // Trigger a model status check
                setTimeout(checkModelStatus, 2000);
            }
        } catch (error) {
            console.error('Error fetching download progress:', error);
        }
    }, 1000);
}

// Trigger model download
async function triggerModelDownload(modelId) {
    // First check if model is already available or was recently downloaded
    try {
        const statusResponse = await fetch('/api/model-status?modelId=' + modelId);
        const statusData = await statusResponse.json();

        // If model is already available, don't download again
        if (statusData.actual_status === 'ok') {
            console.log(`Model ${modelId} is already available, no download needed`);
            hideLoadingOverlay();
            return;
        }

        // If download just completed, don't start again
        if (statusData.download_progress && 
            statusData.download_progress.progress === 100 && 
            !statusData.download_progress.downloading && 
            statusData.download_progress.model === modelId) {

            console.log(`Model ${modelId} download was recently completed`);
            hideLoadingOverlay();
            return;
        }

        // If already downloading this model, just start tracking
        if (statusData.download_progress && 
            statusData.download_progress.downloading && 
            statusData.download_progress.model === modelId) {

            console.log(`Model ${modelId} is already downloading, starting progress tracking`);
            startProgressTracking();
            return;
        }

        // Proceed with download request
        const response = await fetch('/api/download-model', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ modelId: modelId })
        });
        const data = await response.json();
        console.log('Download request response:', data);

        if (data.success) {
            // Start tracking progress
            startProgressTracking();
        } else {
            console.error('Download request was unsuccessful:', data.error);
            hideLoadingOverlay(); // Hide loading overlay if download fails
        }
    } catch (error) {
        console.error('Error in triggerModelDownload:', error);
        hideLoadingOverlay(); // Hide loading overlay on error
    }
}

// Hide loading overlay
function hideLoadingOverlay() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.opacity = '0';
        setTimeout(() => {
            overlay.style.display = 'none';
        }, 300);
    }
}

// Welcome the user with an assistant message
function welcomeUser() {
    const chatMessages = document.getElementById('chat-messages');

    // Only add welcome message if the chat is empty
    if (chatMessages && chatMessages.childElementCount <= 1) { // 1 to account for welcome screen
        // Remove welcome screen
        const welcomeScreen = document.querySelector('.welcome-screen');
        if (welcomeScreen) {
            welcomeScreen.style.display = 'none';
        }

        // Add assistant welcome message
        addMessage('assistant', 'Welcome to the Terraform LLM Assistant! I can help you with Terraform, AWS, infrastructure as code, and cloud architecture. How can I assist you today?');
    }
}

// Send a message
function sendMessage() {
    const messageInput = document.getElementById('message-input');
    if (!messageInput) return;

    const message = messageInput.value.trim();
    if (message === '') return;

    // Remove welcome screen if visible
    const welcomeScreen = document.querySelector('.welcome-screen');
    if (welcomeScreen) {
        welcomeScreen.style.display = 'none';
    }

    // Add user message
    addMessage('user', message);

    // Clear input
    messageInput.value = '';
    messageInput.focus();

    // Add loading indicator
    const loadingId = `loading-${Date.now()}`;
    addLoadingIndicator(loadingId);

    // Send to backend
    fetch('/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(data => {
        // Remove loading
        removeLoadingIndicator(loadingId);

        if (data.success) {
            addMessage('assistant', data.response);
        } else {
            addMessage('assistant', `Error: ${data.error || 'Unknown error occurred'}`);
        }
    })
    .catch(error => {
        removeLoadingIndicator(loadingId);
        addMessage('assistant', `Error: ${error.message || 'Failed to communicate with the server'}`);
    });
}

// Add a loading indicator
function addLoadingIndicator(id) {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;

    const loadingDiv = document.createElement('div');
    loadingDiv.id = id;
    loadingDiv.className = 'message assistant-message loading';
    loadingDiv.innerHTML = '<div class="loading-dots">Thinking<span class="dots"></span></div>';
    chatMessages.appendChild(loadingDiv);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Remove loading indicator
function removeLoadingIndicator(id) {
    const loadingDiv = document.getElementById(id);
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

// Add a message to the chat
function addMessage(sender, content) {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;

    // Store in history
    chatHistory.push({ sender, content, timestamp: new Date() });

    // Create message element
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;

    // Process content based on sender
    if (sender === 'assistant') {
        // For assistant messages, we'll use markdown rendering
        // First include the raw content for potential copy-paste
        const rawContent = document.createElement('div');
        rawContent.className = 'message-raw';
        rawContent.style.display = 'none';
        rawContent.textContent = content;
        messageDiv.appendChild(rawContent);

        // Then add the rendered content
        const renderedContent = document.createElement('div');
        renderedContent.className = 'message-content';

        // Process markdown with code highlighting
        // This is a simplified version - in production you'd use a proper markdown library
        let processedContent = content
            .replace(/```([a-z]*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');

        renderedContent.innerHTML = `<p>${processedContent}</p>`;
        messageDiv.appendChild(renderedContent);
    } else {
        // For user messages, just escape HTML and preserve line breaks
        const userContent = document.createElement('div');
        userContent.className = 'message-content';
        userContent.textContent = content;
        messageDiv.appendChild(userContent);
    }

    // Add to chat
    chatMessages.appendChild(messageDiv);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Reset conversation
function resetConversation() {
    // Clear chat history
    chatHistory = [];

    // Clear chat messages
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        // Keep only the welcome screen
        const welcomeScreen = document.querySelector('.welcome-screen');
        chatMessages.innerHTML = '';

        if (welcomeScreen) {
            // Clone and re-add the welcome screen
            const newWelcomeScreen = welcomeScreen.cloneNode(true);
            chatMessages.appendChild(newWelcomeScreen);

            // Re-attach event listeners to example cards
            const exampleCards = newWelcomeScreen.querySelectorAll('.example-card');
            exampleCards.forEach(card => {
                const example = card.getAttribute('data-example') || card.querySelector('p').textContent;
                card.onclick = () => sendExample(example);
            });
        } else {
            // If no welcome screen exists, add the assistant welcome message
            welcomeUser();
        }
    }

    // Clear input
    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        messageInput.value = '';
        messageInput.focus();
    }
}

// Send an example from the welcome screen
function sendExample(text) {
    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        messageInput.value = text;
        sendMessage();
    }
}

// Get loading timeout from server or use default
const loadingTimeout = window.LOADING_TIMEOUT || 20000; // Default 20 seconds if not set

// Force hide loading overlay after a maximum wait time
setTimeout(() => {
    console.log(`Forcing removal of loading overlay after ${loadingTimeout}ms timeout`);
    hideLoadingOverlay();

    // Also clear any ongoing intervals
    if (progressCheckInterval) clearInterval(progressCheckInterval);
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        // Reset to less frequent checks
        statusCheckInterval = setInterval(checkModelStatus, 30000);
    }
}, loadingTimeout);
                    <div class="example-card" onclick="sendExample('Create an RDS database with backups and security')">
                        <div class="example-icon"><i class="fa-solid fa-database"></i></div>
                        <div class="example-content">
                            <h3>Database</h3>
                            <p>Create an RDS database with backups and security</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // Global function to send example prompts
    window.sendExample = function(text) {
        if (!messageInput) return;

        messageInput.value = text;

        // Trigger auto-resize
        messageInput.dispatchEvent(new Event('input'));

        // Send the message
        sendMessage();
    };

    // Track model download attempts to prevent multiple requests
    const modelDownloadAttempts = {};

    // Function to initiate model download
    function initiateModelDownload(modelId) {
        // Don't try to download more than once every minute
        const now = Date.now();
        const lastAttempt = modelDownloadAttempts[modelId] || 0;

        if (now - lastAttempt < 60000) {
            console.log(`Skipping download request for ${modelId}, last attempt was ${Math.round((now - lastAttempt)/1000)}s ago`);
            return;
        }

        // Record this attempt
        modelDownloadAttempts[modelId] = now;

        console.log(`Initiating download for model: ${modelId}`);

        fetch('/api/download-model', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ modelId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`Model download initiated: ${data.message}`);
            } else {
                console.error(`Failed to initiate model download: ${data.error}`);
            }
        })
        .catch(error => {
            console.error('Error initiating model download:', error);
        });
    }

    // Initialize the application
    initializeApp();
});
