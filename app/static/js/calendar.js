document.addEventListener('DOMContentLoaded', function() {
    // Encontre todos os botões ou links de conexão com o Google Calendar
    const googleAuthButtons = document.querySelectorAll('.google-calendar-auth');
    
    if (googleAuthButtons) {
        googleAuthButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                // Use a URL correta para a autenticação
                window.location.href = '/api/calendar/google/auth';
            });
        });
    }
}); 