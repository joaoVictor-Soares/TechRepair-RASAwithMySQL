from .connector_db import get_db_connection
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

class ActionCadastraChamados(Action):
    def name(self) -> Text:
        return "action_cadastrar_chamado"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Coleta dos dados salvos nos slots pelo Form
        nome = tracker.get_slot("nome")
        telefone = tracker.get_slot("telefone")
        modelo_completo = tracker.get_slot("modelo")
        problema = tracker.get_slot("problema")
        
        # Tratamento inteligente para separar Modelo e Marca se o usuário digitar "Modelo (Marca)"
        marca = "Não informada"
        modelo = modelo_completo
        if modelo_completo and "(" in modelo_completo and ")" in modelo_completo:
            try:
                partes = modelo_completo.split("(")
                modelo = partes[0].strip()
                marca = partes[1].replace(")", "").strip()
            except Exception:
                modelo = modelo_completo

        try:
            # Utiliza o gerenciador de contexto do db_connector / connector_db
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # 1. Verifica se o cliente já existe pelo telefone
                    sql_check_cliente = "SELECT id FROM clientes WHERE telefone = %s"
                    cursor.execute(sql_check_cliente, (telefone,))
                    cliente = cursor.fetchone()
                    
                    if cliente:
                        # Se já existir, recupera o ID cadastrado
                        cliente_id = cliente[0]  # Assume cursor padrão (tuple)
                    else:
                        # Se não existir, realiza o INSERT incluindo o campo 'email' obrigatório
                        sql_ins_cliente = "INSERT INTO clientes (nome, telefone, email) VALUES (%s, %s, %s)"
                        cursor.execute(sql_ins_cliente, (nome, telefone, "Nao informado"))
                        cliente_id = cursor.lastrowid
                    
                    # 2. Cria o registro do aparelho na tabela dispositivos
                    sql_ins_dispositivo = "INSERT INTO dispositivos (cliente_id, modelo, marca) VALUES (%s, %s, %s)"
                    cursor.execute(sql_ins_dispositivo, (cliente_id, modelo, marca))
                    dispositivo_id = cursor.lastrowid
                    
                    # 3. Busca dinamicamente o ID de um técnico cadastrado no banco
                    cursor.execute("SELECT id FROM tecnicos LIMIT 1")
                    tecnico_registro = cursor.fetchone()
                    
                    # Se houver técnico, pega o ID dele; caso contrário, usa 1 por segurança
                    tecnico_id = tecnico_registro[0] if tecnico_registro else 1
                    
                    # 4. Abre uma nova ordem de serviço incluindo o 'tecnicos_id' obrigatório
                    sql_ins_os = """
                        INSERT INTO ordens_servico (dispositivo_id, tecnicos_id, descricao_problema, status, data_abertura) 
                        VALUES (%s, %s, %s, 'Aguardando', NOW())
                    """
                    cursor.execute(sql_ins_os, (dispositivo_id, tecnico_id, problema))
                    os_id = cursor.lastrowid
                    
                    # Confirma a transação no banco de dados
                    conn.commit()
                    
                    # Resposta de confirmação para o usuário
                    dispatcher.utter_message(text=f"Chamado #{os_id} aberto com sucesso! Status inicial: Aguardando.")
                    
        except Exception as e:
            print(f"Erro na Action Cadastrar Chamado: {e}")
            dispatcher.utter_message(text="Desculpe, ocorreu um erro interno ao salvar o seu chamado. Tente novamente.")
        
        # Limpa os slots temporários do formulário para os próximos atendimentos
        return [SlotSet("nome", None), SlotSet("modelo", None), SlotSet("problema", None)]


class ActionConsultarStatus(Action):
    def name(self) -> Text:
        return "action_consultar_status"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        id_ordem = tracker.get_slot("id_ordem")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Executa o JOIN entre ordens_servico, dispositivos e clientes
                    # Permite buscar tanto pelo ID da Ordem quanto pelo Telefone do cliente
                    sql = """
                        SELECT d.modelo, d.marca, os.status 
                        FROM ordens_servico os
                        JOIN dispositivos d ON os.dispositivo_id = d.id
                        JOIN clientes c ON d.cliente_id = c.id
                        WHERE os.id = %s OR c.telefone = %s
                        ORDER BY os.id DESC LIMIT 1
                    """
                    cursor.execute(sql, (id_ordem, id_ordem))
                    result = cursor.fetchone()
                    
                    if result:
                        modelo, marca, status = result[0], result[1], result[2]
                        # Retorna o status formatado conforme esperado
                        dispatcher.utter_message(text=f"Seu {modelo} ({marca}) está: {status}.")
                    else:
                        # Tratamento de erro obrigatório para ID ou Telefone inexistente
                        dispatcher.utter_message(text="Nenhuma ordem encontrada com este ID. Verifique o número e tente novamente.")
                        
        except Exception as e:
            print(f"Erro na Action Consultar Status: {e}")
            # Garante que o bot capture a exceção sem travar a aplicação
            dispatcher.utter_message(text="Nenhuma ordem encontrada com este ID. Verifique o número e tente novamente.")
            
        return [SlotSet("id_ordem", None)]


class ActionAtualizarEmail(Action):
    def name(self) -> Text:
        return "action_atualizar_email"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        telefone = tracker.get_slot("telefone")
        novo_email = tracker.get_slot("novo_email")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Executa o UPDATE na tabela clientes filtrando pelo telefone
                    sql = "UPDATE clientes SET email = %s WHERE telefone = %s"
                    cursor.execute(sql, (novo_email, telefone))
                    conn.commit()
                    
                    # Confirmação de sucesso
                    dispatcher.utter_message(text="E-mail updated com sucesso!")
                    
        except Exception as e:
            print(f"Erro na Action Atualizar Email: {e}")
            dispatcher.utter_message(text="Não foi possível atualizar o e-mail no momento. Verifique os dados fornecidos.")
            
        return []