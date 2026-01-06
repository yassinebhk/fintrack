/**
 * AI Advisor Chat Module
 */

// Use the global API_BASE_URL from app.js (loaded first)
const AI_API = (window.API_BASE_URL || 'http://localhost:8000/api') + '/ai/chat';
let isTyping = false;

/**
 * Send a message to the AI
 */
async function sendMessage(event) {
    if (event) event.preventDefault();
    
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message || isTyping) return;
    
    const includePortfolio = document.getElementById('includePortfolio').checked;
    
    // Clear input
    input.value = '';
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Show typing indicator
    showTypingIndicator();
    
    try {
        const response = await fetch(AI_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: message,
                include_portfolio: includePortfolio
            })
        });
        
        const data = await response.json();
        
        // Remove typing indicator
        hideTypingIndicator();
        
        // Add bot response
        addMessage(data.response, 'bot', data.tokens_used);
        
    } catch (error) {
        hideTypingIndicator();
        addMessage('Lo siento, ha ocurrido un error de conexión. Por favor, verifica que el servidor esté funcionando.', 'bot');
    }
}

/**
 * Add a message to the chat
 */
function addMessage(content, type, tokens = null) {
    const messagesContainer = document.getElementById('chatMessages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;
    
    const avatar = type === 'bot' ? '🤖' : '👤';
    
    // Convert markdown-like formatting to HTML
    const formattedContent = formatMessage(content);
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            ${formattedContent}
            ${tokens ? `<div class="message-meta">Tokens: ${tokens}</div>` : ''}
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Format message content (basic markdown)
 */
function formatMessage(content) {
    // Convert markdown-style formatting
    let formatted = content
        // Bold
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        // Code blocks
        .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
        // Inline code
        .replace(/`(.*?)`/g, '<code>$1</code>')
        // Line breaks
        .replace(/\n/g, '<br>');
    
    // Convert bullet points
    const lines = formatted.split('<br>');
    let inList = false;
    let result = [];
    
    for (const line of lines) {
        if (line.trim().startsWith('- ') || line.trim().startsWith('• ')) {
            if (!inList) {
                result.push('<ul>');
                inList = true;
            }
            result.push(`<li>${line.trim().substring(2)}</li>`);
        } else if (line.trim().match(/^\d+\. /)) {
            if (!inList) {
                result.push('<ol>');
                inList = true;
            }
            result.push(`<li>${line.trim().replace(/^\d+\. /, '')}</li>`);
        } else {
            if (inList) {
                result.push(inList === 'ol' ? '</ol>' : '</ul>');
                inList = false;
            }
            result.push(line);
        }
    }
    if (inList) {
        result.push('</ul>');
    }
    
    return result.join('');
}

/**
 * Show typing indicator
 */
function showTypingIndicator() {
    isTyping = true;
    const messagesContainer = document.getElementById('chatMessages');
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'chat-message bot typing-indicator';
    typingDiv.id = 'typingIndicator';
    typingDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // Disable send button
    document.getElementById('btnSend').disabled = true;
}

/**
 * Hide typing indicator
 */
function hideTypingIndicator() {
    isTyping = false;
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
    
    document.getElementById('btnSend').disabled = false;
}

/**
 * Ask a suggested question
 */
function askSuggestion(question) {
    document.getElementById('chatInput').value = question;
    sendMessage();
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
});

