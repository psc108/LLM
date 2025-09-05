/**
 * LLM Assistant - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
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
    const loadingOverlay = document.getElementById('loading-overlay');

    // Initialize
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
        this.style.height = (this.scrollHeight) + 'px';
    }

    // Check system status
    function checkSystemStatus() {
        fetch('/health')
            .then(response => response.json())
            .then(data => {
                updateStatusUI(data);

                // Hide loading overlay once we've checked status
                if (loadingOverlay) {
                    loadingOverlay.classList.add('hidden');
                    setTimeout(() => {
                        loadingOverlay.style.display = 'none';
                    }, 300);
                }
            })
            .catch(error => {
                console.error('Health check failed:', error);
                updateStatusUI({ actual_status: 'error', error: 'Connection failed' });

                // Still hide loading overlay after a failed check
                if (loadingOverlay) {
                    loadingOverlay.classList.add('hidden');
                    setTimeout(() => {
                        loadingOverlay.style.display = 'none';
                    }, 300);
                }
            });
    }

    // Update status UI based on health check
    function updateStatusUI(data) {
        if (!statusIndicator || !statusText) return;

        // Update model name if available
        if (modelName && data.model) {
            modelName.textContent = data.model;
        }

        // Update status indicator
        statusIndicator.className = 'status-indicator';

        switch (data.actual_status) {
            case 'ok':
                statusIndicator.classList.add('active');
                statusText.textContent = 'Active';
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

        // Send to API
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        })
        .then(response => response.json())
        .then(data => {
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
            console.error('API error:', error);

            // Remove loading message
            if (loadingMessage) {
                loadingMessage.remove();
            }

            // Add error message
            addMessageToChat('Sorry, there was an error communicating with the server. Please try again.', 'assistant');
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
        messageTime.textContent = new Date().toLocaleTimeString();

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
        messageBubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

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
        // Replace code blocks with formatted HTML
        return content.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, language, code) => {
            language = language || 'plaintext';
            return `<pre><code class="language-${language.trim()}">${code.trim()}</code></pre>`;
        });
    }

    // Reset chat - clear all messages and show welcome screen
    function resetChat() {
        if (!chatMessages) return;

        // Clear all messages
        chatMessages.innerHTML = `
            <div class="welcome-screen">
                <div class="welcome-header">
                    <h2>Welcome to LLM Assistant</h2>
                    <p>Your AI companion for infrastructure and cloud architecture</p>
                </div>

                <div class="examples-grid">
                    <div class="example-card" onclick="sendExample('Create an S3 bucket with versioning and encryption')">
                        <div class="example-icon"><i class="fa-solid fa-cube"></i></div>
                        <div class="example-content">
                            <h3>S3 Storage</h3>
                            <p>Create an S3 bucket with versioning and encryption</p>
                        </div>
                    </div>

                    <div class="example-card" onclick="sendExample('Set up a VPC with public and private subnets')">
                        <div class="example-icon"><i class="fa-solid fa-network-wired"></i></div>
                        <div class="example-content">
                            <h3>Networking</h3>
                            <p>Set up a VPC with public and private subnets</p>
                        </div>
                    </div>

                    <div class="example-card" onclick="sendExample('Deploy EC2 instances with autoscaling')">
                        <div class="example-icon"><i class="fa-solid fa-server"></i></div>
                        <div class="example-content">
                            <h3>Compute</h3>
                            <p>Deploy EC2 instances with autoscaling</p>
                        </div>
                    </div>

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

    // Initialize the application
    initializeApp();
});
