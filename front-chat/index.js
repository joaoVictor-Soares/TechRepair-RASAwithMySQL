const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');

// URL do Rasa
const RASA_URL = 'http://localhost:5005/webhooks/rest/webhook';

// Adiciona mensagem no chat
function addMessage(message, sender) {
  const messageElement = document.createElement('div');

  messageElement.classList.add('message');

  if (sender === 'user') {
    messageElement.classList.add('user-message');
  } else {
    messageElement.classList.add('bot-message');
  }

  messageElement.textContent = message;

  chatMessages.appendChild(messageElement);

  // Scroll automático
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Envia mensagem para o Rasa
async function sendMessage() {
  const message = userInput.value.trim();

  if (message === '') return;

  // Mostra mensagem do usuário
  addMessage(message, 'user');

  // Limpa input
  userInput.value = '';

  try {
    const response = await fetch(RASA_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        sender: 'usuario',
        message: message
      })
    });

    const data = await response.json();

    // Respostas do bot
    data.forEach(item => {
      if (item.text) {
        addMessage(item.text, 'bot');
      }
    });

  } catch (error) {
    console.error(error);

    addMessage(
      'Erro ao conectar com o servidor Rasa.',
      'bot'
    );
  }
}

// Clique no botão
sendButton.addEventListener('click', sendMessage);

// Enter no teclado
userInput.addEventListener('keydown', function(event) {
  if (event.key === 'Enter') {
    sendMessage();
  }
});