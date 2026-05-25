import streamlit as st
import requests  # Subsistema cliente HTTP para consumo de Webhooks externos
import uuid      # Provedor de Identificadores Únicos Universais (UUID) para persistência de escopo

# URI de comunicação do Endpoint REST exposto pela instância do Rasa Open Source
RASA_URL = 'http://localhost:5005/webhooks/rest/webhook'

# Configuração global de metadados da viewport e do documento HTML no ecossistema Streamlit
st.set_page_config(page_title="Atendimento ao cliente")
st.title("Suporte ao Cliente - TechRepair")
st.caption("Conectado ao Rasa open source")  # Elemento descritivo de infraestrutura de microsserviço

# pipeline de Gerenciamento de Estado Reativo (Session State Management)

# Instanciação lazy do identificador de sessão (sender_id) para isolamento de contexto (multi-tenant local)
if 'sender_id' not in st.session_state:
    st.session_state.sender_id = str(uuid.uuid4())

# Inicialização da estrutura de dados linear (Array/List) de buffer para o histórico de interações
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Camada de Renderização Histórica (Presentation Layer)

# Itera sobre o buffer de mensagens e reconstrói a árvore de componentes visuais conforme os papéis atribuídos
for msg in st.session_state.messages:
    with st.chat_message(msg['role']):
        st.markdown(msg['content'])

# Bloco de Captura de Eventos e Input I/O do Usuário

# Intercepta a submissão de dados na Viewport utilizando atribuição por operador de morsa (walrus operator)
if prompt := st.chat_input('Digite sua mensagem'):
    # Persiste o payload de entrada do usuário no buffer mutável da sessão
    st.session_state.messages.append({'role': 'user', 'content': prompt})

    # Renderização síncrona imediata do componente visual do usuário para otimização de Latência Percebida
    with st.chat_message('user'):
        st.markdown(prompt)

    # Contexto assíncrono para processamento, consumo de API e resposta da IA receptora
    with st.chat_message('assistant'):
        # Threading/Spinner visual simulando estado de processamento/digitação (Feedback de UX)
        with st.spinner('Processando resposta...'):
            try:
                # Dispatch da requisição HTTP POST para o gateway de webhook do Rasa
                response = requests.post(
                    RASA_URL,
                    json={'sender': st.session_state.sender_id, 'message': prompt},
                    timeout=10  # SLA de tolerância máxima da requisição (Gargalo de I/O)
                )

                # Deserialização do payload JSON contido no corpo da resposta HTTP
                bot_msgs = response.json()

                # Processamento da coleção de payloads de resposta estruturadas
                if bot_msgs:
                    for bot_msg in bot_msgs:
                        text = bot_msg.get('text', '')  # Extração segura de propriedades via dicionário
                        if text:
                            # Mutação de estado: Acopla a resposta ao histórico consolidado da sessão
                            st.session_state.messages.append({'role': 'assistant', 'content': text})
                            # Renderização na camada de exibição atual
                            st.markdown(text)
                else:
                    # Tratamento de exceção de dados: Resposta nula ou payload vazio do interpretador Rasa
                    texto_vazio = '(Bot não respondeu)'
                    st.session_state.messages.append({'role': 'assistant', 'content': texto_vazio})
                    st.markdown(texto_vazio)

            # Barreira de contenção contra falhas de infraestrutura de rede (Network Fallback)
            except requests.exceptions.ConnectionError:
                # Feedback visual de criticidade: Instância do Rasa indisponível na porta configurada
                st.error('Não foi possível conectar ao Rasa. Certifique-se de que ele está rodando com o comando rasa run.')
            except requests.exceptions.Timeout:
                # Feedback de quebra de SLA por timeout de resposta excedido
                st.error('O Rasa demorou a responder...')
                
    # Força o recarregamento reativo da árvore de componentes (Rerun loop) para consistência visual
    st.rerun()

# Divisor estrutural de seção para elementos administrativos da interface
st.markdown("---")

# Rotina de Reset de Estado da Sessão (Purge Mechanism)
if st.button('Limpar Conversa'):
    st.session_state.messages = []                  # Efetua o flush/limpeza do buffer de mensagens
    st.session_state.sender_id = str(uuid.uuid4())  # Rotaciona a chave de sessão (Gera novo ciclo de conversação)
    st.rerun()                                      # Redireciona a renderização para o estado inicial limpo