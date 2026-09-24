document.addEventListener('DOMContentLoaded', function() {
    // Encontre todos os botões ou links de conexão com o Google Calendar
    const googleAuthButtons = document.querySelectorAll('.google-calendar-auth');
    
    if (googleAuthButtons) {
        googleAuthButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                console.log('Iniciando autenticação com o Google Calendar');
                // Use a URL correta para a autenticação (usando a rota web)
                fetch('/calendar/connect/google')
                    .then(response => {
                        if (response.redirected) {
                            console.log('Redirecionando para:', response.url);
                            window.location.href = response.url;
                        } else {
                            return response.json().then(data => {
                                console.log('Resposta:', data);
                                if (data.auth_url) {
                                    console.log('Redirecionando para URL de autenticação:', data.auth_url);
                                    window.location.href = data.auth_url;
                                }
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Erro ao iniciar autenticação:', error);
                    });
            });
        });
    }
}); 