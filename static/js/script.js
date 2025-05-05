// JavaScript for SlamDunkChat.com chat UI

// Get DOM elements
const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');

// Add event listeners for sending messages
sendButton.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

// Send user message to /chat endpoint and display response
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return; // Ignore empty messages

    // Append user message
    appendMessage('user', `You: ${message}`);
    messageInput.value = ''; // Clear input

    try {
        // Send POST request to /chat
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        const data = await response.json();
        // Determine CSS class based on response_source
        const grokClass = data.response_source === 'search_nba_data' ? 'grok-search-nba-data' : 
                         data.response_source === 'deep_search_query' ? 'grok-deep-search' : 'grok';
        // Append Grok response
        appendMessage(grokClass, `Grok: ${data.grok}`);
    } catch (error) {
        console.error('Error:', error);
        // Append error message
        appendMessage('grok-error', 'Grok: Sorry, something went wrong. Try again later.');
    }
}

// Append message to chat container with specified class
function appendMessage(type, text) {
    const p = document.createElement('p');
    p.className = type; // Apply class (user, grok-search-nba-data, grok-deep-search, grok-error)
    p.textContent = text;
    chatContainer.appendChild(p);
    chatContainer.scrollTop = chatContainer.scrollHeight; // Auto-scroll to bottom
}

// Format dates for betting suggestions (e.g., "2025-05-04" -> "May 4, 2025")
function formatDate(dateStr) {
    if (!dateStr || dateStr === 'N/A') return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}