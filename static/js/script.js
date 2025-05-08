document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;

        // Add user message
        const userDiv = document.createElement('div');
        userDiv.className = 'mb-2 text-primary';
        userDiv.innerHTML = `<strong>You:</strong> ${message}`;
        chatMessages.appendChild(userDiv);

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });
            const data = await response.json();

            // Add Grok response
            const grokDiv = document.createElement('div');
            grokDiv.className = `mb-2 ${data.is_grok_search ? 'text-success' : 'text-primary'}`;
            grokDiv.innerHTML = `<strong>Grok:</strong> ${data.grok}`;
            chatMessages.appendChild(grokDiv);

            // Add betting suggestions only for explicit betting/odds queries
            if (data.bets && data.bets.length > 0 && 
                (message.toLowerCase().includes('bet') || 
                 message.toLowerCase().includes('odds'))) {
                data.bets.forEach(bet => {
                    const betDiv = document.createElement('div');
                    betDiv.className = 'mb-2 text-muted';
                    betDiv.innerHTML = `<strong>Bet:</strong> ${bet.game}, ${bet.date}<br>` +
                        Object.entries(bet.moneyline).map(([team, odds]) => `${team}: ${odds}`).join('<br>');
                    chatMessages.appendChild(betDiv);
                });
            }

            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } catch (error) {
            console.error('Error:', error);
            const errorDiv = document.createElement('div');
            errorDiv.className = 'mb-2 text-danger';
            errorDiv.innerHTML = `<strong>Error:</strong> Failed to get response. Please try again.`;
            chatMessages.appendChild(errorDiv);
        }

        userInput.value = '';
    });
});