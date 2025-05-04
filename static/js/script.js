// JavaScript for SlamDunkChat.com
const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');

sendButton.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    appendMessage('user', `You: ${message}`);
    messageInput.value = '';

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        const data = await response.json();
        const grokClass = data.is_grok_search ? 'grok-search' : 'grok';
        appendMessage(grokClass, `Grok: ${data.grok}`);
    } catch (error) {
        console.error('Error:', error);
        appendMessage('grok', 'Grok: Sorry, something went wrong. Try again later.');
    }
}

function appendMessage(type, text) {
    const p = document.createElement('p');
    p.className = type;
    p.textContent = text;
    chatContainer.appendChild(p);
    chatContainer.scrollTop = chatContainer.scrollHeight; // Auto-scroll
}

function formatDate(dateStr) {
    if (!dateStr || dateStr === 'N/A') return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}