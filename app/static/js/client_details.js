// Adicione este script à página de detalhes do cliente

// Função para agendar contato no calendário
function scheduleContactWithClient() {
    const clientId = document.getElementById('clientId').value;
    const clientName = document.getElementById('clientName').textContent;
    const clientCompany = document.getElementById('clientCompany').textContent;
    
    // Modal para configurar o evento
    const modal = new bootstrap.Modal(document.getElementById('scheduleContactModal'));
    modal.show();
    
    // Preencher informações do cliente no modal
    document.getElementById('eventTitle').value = `Contato com ${clientName}`;
    document.getElementById('eventDescription').value = `Reunião de acompanhamento com ${clientName} da empresa ${clientCompany}`;
    
    // Configurar manipulador de eventos para o botão de agendamento
    document.getElementById('saveEvent').addEventListener('click', function() {
        const title = document.getElementById('eventTitle').value;
        const description = document.getElementById('eventDescription').value;
        const startTime = document.getElementById('eventStartTime').value;
        const endTime = document.getElementById('eventEndTime').value;
        const location = document.getElementById('eventLocation').value;
        const calendarType = document.querySelector('input[name="calendarType"]:checked').value;
        
        const eventData = {
            title: title,
            description: description,
            start_time: startTime,
            end_time: endTime,
            location: location,
            client_id: clientId
        };
        
        // Enviar para a API adequada com base no tipo de calendário selecionado
        let endpoint = '';
        if (calendarType === 'google') {
            endpoint = '/api/calendar/google/event';
        } else if (calendarType === 'outlook') {
            endpoint = '/api/calendar/outlook/event';
        }
        
        fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(eventData)
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error('Falha ao criar evento');
            }
        })
        .then(data => {
            modal.hide();
            
            // Atualizar a última data de contato
            fetch(`/api/clients/${clientId}/last-contact`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ last_contact_date: new Date().toISOString() })
            })
            .then(() => {
                alert('Evento agendado com sucesso!');
                // Opcional: recarregar a página para mostrar a data de contato atualizada
                window.location.reload();
            });
        })
        .catch(error => {
            console.error('Erro ao agendar evento:', error);
            alert('Erro ao agendar evento. Verifique se você conectou sua conta do calendário.');
        });
    });
}

// Adicionar manipuladores de eventos aos botões
document.addEventListener('DOMContentLoaded', function() {
    const scheduleContactBtn = document.getElementById('scheduleContactBtn');
    if (scheduleContactBtn) {
        scheduleContactBtn.addEventListener('click', scheduleContactWithClient);
    }
    
    // Enviar lembrete manual para contatar o cliente
    const sendReminderBtn = document.getElementById('sendReminderBtn');
    if (sendReminderBtn) {
        sendReminderBtn.addEventListener('click', function() {
            const clientId = document.getElementById('clientId').value;
            
            fetch(`/api/notifications/client-reminder/${clientId}`, {
                method: 'POST'
            })
            .then(response => {
                if (response.ok) {
                    alert('Lembrete enviado com sucesso!');
                } else {
                    throw new Error('Falha ao enviar lembrete');
                }
            })
            .catch(error => {
                console.error('Erro ao enviar lembrete:', error);
                alert('Erro ao enviar lembrete. Tente novamente.');
            });
        });
    }
}); 