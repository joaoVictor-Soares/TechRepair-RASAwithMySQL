from .connector_db import get_db_connection
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

class ActionCadastraChamados(Action):
    """
    Componente Custom Action do Rasa SDK responsável pelo fluxo transacional de 
    abertura de ordens de serviço e persistência relacional de novos clientes e dispositivos.
    """

    def name(self) -> Text:
        """
        Retorna o identificador único da action mapeado no domínio da aplicação.
        """
        return "action_cadastrar_chamado"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Executa a pipeline de cadastro extraindo dados de slots, executando processos
        de limpeza de strings e persistindo registros encadeados no banco de dados.
        """
        # Extração de metadados persistidos temporariamente nos slots do Tracker
        nome = tracker.get_slot("nome")
        telefone = tracker.get_slot("telefone")
        modelo_completo = tracker.get_slot("modelo")
        problema = tracker.get_slot("problema")
        
        # Algoritmo de parsing e sanitização para extração estruturada de Marca e Modelo
        marca = "Não informada"
        modelo = modelo_completo
        if modelo_completo and "(" in modelo_completo and ")" in modelo_completo:
            try:
                partes = modelo_completo.split("(")
                modelo = partes[0].strip()
                marca = partes[1].replace(")", "").strip()
            except Exception:
                # Mecanismo de fallback: preserva o valor bruto caso ocorra erro no split
                modelo = modelo_completo

        try:
            # Inicialização do bloco do Gerenciador de Contexto (Context Manager) para conexão ao SGDB
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # 1. Validação de Idoneidade/Existência do Cliente via chave de negócio (Telefone)
                    sql_check_cliente = "SELECT id FROM clientes WHERE telefone = %s"
                    cursor.execute(sql_check_cliente, (telefone,))
                    cliente = cursor.fetchone()
                    
                    if cliente:
                        # Idempotência: Recupera o ID existente mitigando registros duplicados
                        cliente_id = cliente[0]  
                    else:
                        # Inserção de registro na tabela dimensional 'clientes'
                        sql_ins_cliente = "INSERT INTO clientes (nome, telefone, email) VALUES (%s, %s, %s)"
                        cursor.execute(sql_ins_cliente, (nome, telefone, "Nao informado"))
                        cliente_id = cursor.lastrowid # Captura da PK gerada via Auto-Increment
                    
                    # 2. Inserção de dependência na tabela relacional 'dispositivos' (Foreign Key -> Clientes)
                    sql_ins_dispositivo = "INSERT INTO dispositivos (cliente_id, modelo, marca) VALUES (%s, %s, %s)"
                    cursor.execute(sql_ins_dispositivo, (cliente_id, modelo, marca))
                    dispositivo_id = cursor.lastrowid
                    
                    # 3. Resolução dinâmica de dependência obrigatória de Recursos Humanos (Técnicos)
                    cursor.execute("SELECT id FROM tecnicos LIMIT 1")
                    tecnico_registro = cursor.fetchone()
                    
                    # Definição de Fallback Seguro para evitar quebras por restrição Foreign Key (Integridade Referencial)
                    tecnico_id = tecnico_registro[0] if tecnico_registro else 1
                    
                    # 4. Criação da Ordem de Serviço na tabela de fatos 'ordens_servico'
                    sql_ins_os = """
                        INSERT INTO ordens_servico (dispositivo_id, tecnicos_id, descricao_problema, status, data_abertura) 
                        VALUES (%s, %s, %s, 'Aguardando', NOW())
                    """
                    cursor.execute(sql_ins_os, (dispositivo_id, tecnico_id, problema))
                    os_id = cursor.lastrowid
                    
                    # Confirmação atômica de todas as operações na transação (ACID compliance)
                    conn.commit()
                    
                    # Despacho da camada de apresentação ao usuário com identificador público do processo
                    dispatcher.utter_message(text=f"Chamado #{os_id} aberto com sucesso! Status inicial: Aguardando.")
                    
        except Exception as e:
            # Tratamento genérico de exceções: Registra no log de auditoria da aplicação
            print(f"Erro na Action Cadastrar Chamado: {e}")
            # Emissão de resposta amigável para mitigar impactos na experiência do usuário (UX)
            dispatcher.utter_message(text="Desculpe, ocorreu um erro interno ao salvar o seu chamado. Tente novamente.")
        
        # Estado de descarte: Efetua o Reset dos slots temporários para o ciclo de vida do próximo atendimento
        return [SlotSet("nome", None), SlotSet("modelo", None), SlotSet("problema", None)]


class ActionConsultarStatus(Action):
    """
    Componente Custom Action responsável por realizar operações de leitura orientada (SELECT)
    com junções de tabelas para fornecer visibilidade de processos de reparo ativos.
    """

    def name(self) -> Text:
        """
        Retorna o identificador único mapeado para fins de roteamento de intenções.
        """
        return "action_consultar_status"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Consulta os dados consolidados da ordem de serviço filtrando por chaves primárias ou secundárias.
        """
        id_ordem = tracker.get_slot("id_ordem")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Execução de Inner Join multidimensional buscando unificação de domínios (OS, Dispositivos e Clientes)
                    sql = """
                        SELECT d.modelo, d.marca, os.status 
                        FROM ordens_servico os
                        JOIN dispositivos d ON os.dispositivo_id = d.id
                        JOIN clientes c ON d.cliente_id = c.id
                        WHERE os.id = %s OR c.telefone = %s
                        ORDER BY os.id DESC LIMIT 1
                    """
                    # Parametrização segura contra vetores de ataque por SQL Injection
                    cursor.execute(sql, (id_ordem, id_ordem))
                    result = cursor.fetchone()
                    
                    if result:
                        modelo, marca, status = result[0], result[1], result[2]
                        dispatcher.utter_message(text=f"Seu {modelo} ({marca}) está: {status}.")
                    else:
                        # Tratamento explícito de Regra de Negócio: Registro Inexistente na base
                        dispatcher.utter_message(text="Nenhuma ordem encontrada com este ID. Verifique o número e tente novamente.")
                        
        except Exception as e:
            # Logging de infraestrutura e barreira de contenção contra quebras da pilha de execução
            print(f"Erro na Action Consultar Status: {e}")
            dispatcher.utter_message(text="Nenhuma ordem encontrada com este ID. Verifique o número e tente novamente.")
            
        return [SlotSet("id_ordem", None)]


class ActionAtualizarEmail(Action):
    """
    Componente Custom Action responsável por executar operações de mutação de estado (UPDATE)
    nos dados de contato localizados no repositório de clientes.
    """

    def name(self) -> Text:
        """
        Retorna o identificador único para o mapeamento e acionamento no domínio Rasa.
        """
        return "action_atualizar_email"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Executa a atualização de dados cadastrais de forma direcionada.
        """
        telefone = tracker.get_slot("telefone")
        novo_email = tracker.get_slot("novo_email")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Mutação de estado direcionada por restrição de chave única (Telefone)
                    sql = "UPDATE clientes SET email = %s WHERE telefone = %s"
                    cursor.execute(sql, (novo_email, telefone))
                    
                    # Persistência explícita da instrução de escrita no banco de dados
                    conn.commit()
                    
                    dispatcher.utter_message(text="E-mail atualizado com sucesso!")
                    
        except Exception as e:
            print(f"Erro na Action Atualizar Email: {e}")
            dispatcher.utter_message(text="Não foi possível atualizar o e-mail no momento. Verifique os dados fornecidos.")
            
        return []