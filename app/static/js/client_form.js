// Função para garantir que datas sejam formatadas corretamente com timezone UTC
function formatDateUTC(dateString) {
    try {
        if (!dateString) return null;
        
        // Converter a string de data para um objeto Date
        const date = new Date(dateString);
        
        // Verificar se a data é válida
        if (isNaN(date.getTime())) {
            console.error("Data inválida:", dateString);
            return null;
        }
        
        // Formatar a data no formato ISO com timezone UTC
        return date.toISOString();
    } catch (error) {
        console.error("Erro ao formatar data:", error);
        return null;
    }
}

// Event listener para o formulário
document.addEventListener('DOMContentLoaded', function() {
    const clientForm = document.getElementById('clientForm');
    const clientIdInput = document.getElementById('clientId');
    const clientId = clientIdInput ? clientIdInput.value : null;
    const isEditMode = clientId && clientId !== 'new';
    
    // Se estiver em modo de edição, carregar dados do cliente
    if (isEditMode) {
        console.log("Carregando cliente para edição:", clientId);
        fetch(`/api/v1/clients/${clientId}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro ao carregar dados do cliente');
            }
            return response.json();
        })
        .then(client => {
            // Preencher formulário com dados do cliente
            document.getElementById('name').value = client.name || '';
            document.getElementById('company').value = client.company || '';
            document.getElementById('email').value = client.email || '';
            document.getElementById('phone').value = client.phone || '';
            document.getElementById('status').value = client.status || 'LEAD';
            document.getElementById('sales_potential').value = client.sales_potential || 3;
            
            // Formatar datas para o formato esperado pelos inputs date
            if (client.last_contact) {
                const lastContactDate = new Date(client.last_contact);
                document.getElementById('last_contact').value = lastContactDate.toISOString().split('T')[0];
            }
            
            if (client.next_followup) {
                const nextFollowupDate = new Date(client.next_followup);
                document.getElementById('next_followup').value = nextFollowupDate.toISOString().split('T')[0];
            }
        })
        .catch(error => {
            console.error('Erro ao carregar cliente:', error);
            alert('Erro ao carregar dados do cliente: ' + error.message);
        });
    }
    
    // Listener para submissão do formulário
    clientForm.addEventListener('submit', function(event) {
        event.preventDefault();
        
        // Obter valores do formulário
        const name = document.getElementById('name').value;
        const company = document.getElementById('company').value;
        const email = document.getElementById('email').value;
        const phone = document.getElementById('phone').value;
        const status = document.getElementById('status').value;
        const sales_potential = parseInt(document.getElementById('sales_potential').value);
        const lastContactInput = document.getElementById('last_contact').value;
        const nextFollowupInput = document.getElementById('next_followup').value;
        
        // Formatar datas com timezone UTC
        const last_contact = formatDateUTC(lastContactInput);
        const next_followup = formatDateUTC(nextFollowupInput);
        
        if (!last_contact || !next_followup) {
            alert('Por favor, preencha as datas corretamente.');
            return;
        }
        
        // Construir objeto de dados
        const data = {
            name,
            company,
            email,
            phone,
            status,
            sales_potential,
            last_contact,
            next_followup,
            interaction_history: [],
            pending_tasks: []
        };
        
        console.log("Dados a serem enviados:", data);
        
        // Determinar URL e método com base no modo (criação ou edição)
        const url = isEditMode ? `/api/v1/clients/${clientId}` : '/api/v1/clients/';
        const method = isEditMode ? 'PUT' : 'POST';
        
        // Enviar requisição
        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
        .then(response => {
            console.log("Status da resposta:", response.status);
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.detail || 'Erro ao salvar cliente');
                });
            }
            return response.json();
        })
        .then(result => {
            console.log("Cliente salvo com sucesso:", result);
            window.location.href = '/clients';
        })
        .catch(error => {
            console.error('Erro ao salvar cliente:', error);
            alert('Erro ao salvar cliente: ' + error.message);
        });
    });
}); 