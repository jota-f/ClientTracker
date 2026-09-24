import requests
import json
import os
from datetime import datetime, timedelta

# URL base
base_url = "http://localhost:8000"

# Autenticar e obter token
def get_auth_token():
    try:
        print("Tentando autenticar...")
        login_response = requests.post(
            f"{base_url}/api/auth/login",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "username": "pgswifi@gmail.com",
                "password": "123456"
            }
        )
        
        if login_response.status_code == 200:
            token_data = login_response.json()
            print(f"Autenticação bem-sucedida. Usuário: {token_data.get('user', {}).get('email')}")
            return token_data.get("access_token")
        else:
            print(f"Erro na autenticação: {login_response.status_code}")
            print(f"Detalhes: {login_response.text}")
            return None
    except Exception as e:
        print(f"Exceção na autenticação: {str(e)}")
        return None

# Obter token de autenticação
token = get_auth_token()

if not token:
    print("Não foi possível obter o token. Usando token existente.")
    # Token de autenticação atualizado (obtido de teste anterior)
    token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI2N2Q0ZDVjODAwMzdhMjRmOTc1OGRjNTgiLCJlbWFpbCI6InBnc3dpZmlAZ21haWwuY29tIiwidXNlcm5hbWUiOiJwZ3N3aWZpQGdtYWlsLmNvbSIsInJvbGUiOiJ1c2VyIiwiZXhwIjoxNzQzMzA5NDI2fQ.c_HyPCZ2FRLQ1fV9j4qvv9YSALVSyFnDxLbK29Zs48w"

# URL do endpoint para clientes
url = f"{base_url}/api/v1/clients/"

# Verificar se o token funciona
print("\nVerificando o token...")
check_auth_response = requests.get(
    f"{base_url}/api/auth/check",
    headers={
        "Authorization": f"Bearer {token}"
    }
)
print(f"Status do token: {check_auth_response.status_code}")
print(f"Resposta: {json.dumps(check_auth_response.json(), indent=2)}")

# Datas ISO 8601 com timezone
now = datetime.now().isoformat()
next_week = (datetime.now() + timedelta(days=7)).isoformat()

# Teste 1: Cliente com todos os campos mínimos necessários
print("\n\nTESTE 1: Cliente com campos mínimos")
client_data = {
    "name": "Cliente Teste Minimo",
    "company": "Empresa Teste",
    "email": "teste@teste.com",
    "phone": "123456789",
    "status": "LEAD",
    "sales_potential": 3,
    "last_contact": now,
    "next_followup": next_week,
    "user_id": "67d4d5c80037a24f9758dc58"  # ID do usuário autenticado
}

print("Enviando dados básicos do cliente:")
print(json.dumps(client_data, indent=2))

try:
    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        },
        json=client_data
    )

    print(f"\nStatus code: {response.status_code}")
    
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response text: {response.text}")
except Exception as e:
    print(f"Erro na requisição: {str(e)}")

# Teste 2: Cliente com todos os campos incluindo listas vazias
print("\n\nTESTE 2: Cliente com listas vazias")
client_data_2 = client_data.copy()
client_data_2["name"] = "Cliente Teste Completo"
client_data_2["interaction_history"] = []
client_data_2["pending_tasks"] = []

print("Enviando dados do cliente com listas vazias:")
print(json.dumps(client_data_2, indent=2))

try:
    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        },
        json=client_data_2
    )

    print(f"\nStatus code: {response.status_code}")
    
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response text: {response.text}")
except Exception as e:
    print(f"Erro na requisição: {str(e)}")

# Teste 3: Cliente com uma tarefa e uma interação
print("\n\nTESTE 3: Cliente com tarefas e interações")
client_data_3 = client_data.copy()
client_data_3["name"] = "Cliente Teste Com Histórico"
client_data_3["interaction_history"] = [
    {
        "date": now,
        "type": "EMAIL",
        "notes": "Primeiro contato",
        "outcome": "POSITIVO"
    }
]
client_data_3["pending_tasks"] = [
    {
        "title": "Enviar proposta",
        "due_date": next_week,
        "status": "TODO",
        "description": "Preparar orçamento para envio"
    }
]

print("Enviando dados do cliente com tarefas e interações:")
print(json.dumps(client_data_3, indent=2))

try:
    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        },
        json=client_data_3
    )

    print(f"\nStatus code: {response.status_code}")
    
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response text: {response.text}")
except Exception as e:
    print(f"Erro na requisição: {str(e)}") 