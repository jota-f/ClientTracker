// auth.js - Funções de autenticação do cliente

// Lista de páginas públicas que não requerem autenticação
const PUBLIC_PAGES = ['/login', '/register', '/forgot-password', '/auth-debug', '/auth-test'];

// Adiciona uma função para imprimir o token no console para depuração
function logToken() {
    const token = localStorage.getItem('access_token');
    console.log('Token atual:', token ? token.substring(0, 20) + '...' : 'nenhum');
    console.log('Autenticado?', isAuthenticated());
    return token;
}

// Verifica se a página atual é pública
function isPublicPage(path) {
    // Se um caminho for fornecido, use-o; caso contrário, use o pathname atual
    const currentPath = path || window.location.pathname;
    const isPublic = PUBLIC_PAGES.includes(currentPath);
    console.log('isPublicPage:', currentPath, isPublic);
    return isPublic;
}

// Verifica se o usuário está autenticado
function isAuthenticated() {
    const token = localStorage.getItem('access_token');
    console.log('Verificando autenticação - token presente:', !!token);
    return token !== null;
}

// Obtém o token JWT do localStorage
function getToken() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        console.warn('Token não encontrado no localStorage');
        return null;
    }
    return token;
}

// Obtém os dados do usuário do localStorage
function getUser() {
    const userStr = localStorage.getItem('user');
    if (!userStr) {
        console.warn('Dados de usuário não encontrados no localStorage');
        return null;
    }
    
    try {
        return JSON.parse(userStr);
    } catch (e) {
        console.error('Erro ao parsear dados do usuário:', e);
        return null;
    }
}

// Faz logout do usuário
function logout() {
    console.log('Realizando logout...');
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    window.location.href = '/login';
}

// Redireciona para login se não estiver autenticado
function requireAuth() {
    if (!isAuthenticated()) {
        // Salva a URL atual para redirecionar de volta após o login
        const currentPath = window.location.pathname;
        if (!isPublicPage()) {
            console.log('Redirecionando para login, página atual:', currentPath);
            sessionStorage.setItem('redirect_after_login', currentPath);
            window.location.href = '/login';
            return false;
        }
    }
    return true;
}

// Verifica o estado de autenticação com o servidor e atualiza a UI
async function checkAuthStatus() {
    try {
        console.log('URL atual:', window.location.href);
        console.log('Pathname:', window.location.pathname);
        
        // Se estamos em uma página pública, não precisamos verificar autenticação
        if (isPublicPage()) {
            console.log('Página pública, não é necessário verificar autenticação');
            updateUI(isAuthenticated());
            return isAuthenticated();
        }
        
        // Se não há token no localStorage, reporta como não autenticado
        if (!isAuthenticated()) {
            console.log('Não há token no localStorage');
            updateUI(false);
            return false;
        }
        
        console.log('Verificando token com o servidor...');
        // Verifica com o servidor se o token é válido
        const token = getToken();
        if (!token) {
            console.error('Token não disponível para verificação');
            updateUI(false);
            return false;
        }
        
        const response = await fetch('/api/auth/check', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const data = await response.json();
        console.log('Resposta da verificação do token:', data);
        
        if (!data.authenticated) {
            console.log('Token não é válido no servidor');
            // Token inválido, mas não remova automaticamente - apenas reporta
            updateUI(false);
            return false;
        }
        
        // Atualiza os dados do usuário caso estejam diferentes
        localStorage.setItem('user', JSON.stringify(data.user));
        updateUI(true);
        return true;
    } catch (error) {
        console.error('Erro ao verificar autenticação:', error);
        updateUI(false);
        return false;
    }
}

// Atualiza a UI com base no estado de autenticação
function updateUI(isAuthenticated) {
    try {
        console.log('Atualizando UI - autenticado:', isAuthenticated);
        const loginButtons = document.querySelector('[href="/login"]')?.parentElement;
        const userDropdown = document.querySelector('.relative.group'); // O dropdown do usuário
        
        if (loginButtons && userDropdown) {
            if (isAuthenticated) {
                // Usuário está autenticado
                loginButtons.classList.add('hidden');
                userDropdown.classList.remove('hidden');
                
                // Atualiza o nome do usuário
                const user = getUser();
                if (user) {
                    const usernameElement = userDropdown.querySelector('span');
                    if (usernameElement) {
                        usernameElement.textContent = user.username;
                    }
                }
            } else {
                // Usuário não está autenticado
                loginButtons.classList.remove('hidden');
                userDropdown.classList.add('hidden');
            }
        } else {
            console.warn('Elementos de UI não encontrados: loginButtons=', !!loginButtons, 'userDropdown=', !!userDropdown);
        }
    } catch (error) {
        console.error('Erro ao atualizar UI:', error);
    }
}

// Adiciona o token de autorização a todas as requisições fetch
const originalFetch = window.fetch;
window.fetch = async function(url, options = {}) {
    try {
        console.log('Interceptando fetch para:', url);
        
        // Se não estiver autenticado ou a URL for para login/registro, use fetch normal
        if (!isAuthenticated()) {
            console.log('Não autenticado, usando fetch normal');
            return originalFetch(url, options);
        }
        
        if (url.includes('/api/auth/login') || url.includes('/api/auth/register')) {
            console.log('Requisição de autenticação, usando fetch normal');
            return originalFetch(url, options);
        }
        
        // Cria uma nova instância das options para não modificar o objeto original
        const newOptions = { ...options };
        newOptions.headers = newOptions.headers || {};
        
        // Adiciona o token de autorização no header se não existir
        if (!newOptions.headers['Authorization']) {
            const token = getToken();
            if (token) {
                console.log('Adicionando token de autorização à requisição para:', url);
                newOptions.headers['Authorization'] = `Bearer ${token}`;
                console.log('Headers após adição:', JSON.stringify(newOptions.headers));
            } else {
                console.warn('Não foi possível adicionar token à requisição para:', url);
            }
        }
        
        try {
            // Faz a requisição com o token
            console.log('Enviando requisição com headers:', JSON.stringify(newOptions.headers));
            const response = await originalFetch(url, newOptions);
            
            console.log('Resposta recebida:', url, response.status);
            
            // Se receber 401 Unauthorized, limpa o token e redireciona para login
            if (response.status === 401) {
                console.error('Recebido 401 Unauthorized de:', url);
                // logout(); // Comentado temporariamente para depuração
                console.error('Recebido 401, mas não fazendo logout para depuração');
            }
            
            return response;
        } catch (error) {
            console.error('Erro na requisição:', error);
            throw error;
        }
    } catch (error) {
        console.error('Erro no middleware fetch:', error);
        // Em caso de erro, tenta fazer a requisição original sem modificações
        return originalFetch(url, options);
    }
}

// Adiciona o token às navegações diretas (não-AJAX)
function addTokenToNavigation() {
    document.addEventListener('click', function(e) {
        // Verifica se o clique foi em um link interno
        let target = e.target;
        while (target && target.tagName !== 'A') {
            target = target.parentElement;
        }
        
        if (target && target.tagName === 'A' && 
            target.href && 
            target.href.startsWith(window.location.origin) && 
            !target.getAttribute('data-no-auth')) {
            
            const urlPath = new URL(target.href).pathname;
            console.log('Clique em link interno:', target.href, 'path:', urlPath);
            
            // Páginas públicas não precisam de autenticação
            if (isPublicPage(urlPath)) {
                console.log('Link para página pública, navegação normal');
                return;
            }
            
            // Se não estiver autenticado, redireciona para login
            if (!isAuthenticated()) {
                console.log('Não autenticado, redirecionando para login');
                e.preventDefault();
                sessionStorage.setItem('redirect_after_login', urlPath);
                window.location.href = '/login';
                return;
            }
            
            // Vamos adicionar o token como um cookie para a sessão atual
            const token = getToken();
            if (token) {
                console.log('Adicionando token ao cookie e cabeçalho personalizado');
                
                // Criar um cookie temporário para esta sessão (não é muito seguro, mas é para teste)
                document.cookie = "Authorization=Bearer " + token + "; path=/; SameSite=Strict";
                
                // Adicionar um cabeçalho personalizado através de meta tag
                let meta = document.querySelector('meta[name="x-auth-token"]');
                if (!meta) {
                    meta = document.createElement('meta');
                    meta.name = 'x-auth-token';
                    document.head.appendChild(meta);
                }
                meta.content = token;
                
                // Adiciona um parâmetro de query com um identificador aleatório para evitar cache
                // (não adiciona o token à URL por questões de segurança)
                e.preventDefault();
                const urlObj = new URL(target.href);
                urlObj.searchParams.set('_', Date.now().toString(36));
                
                // Navegação direta para a URL com os parâmetros
                window.location.href = urlObj.toString();
            }
        }
    });
}

// Se estamos em uma página protegida, verifica se temos um token no hash
function checkHashToken() {
    if (!isAuthenticated() && !isPublicPage() && window.location.hash) {
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);
        const token = params.get('token');
        
        if (token) {
            console.log('Token encontrado no hash da URL, salvando...');
            localStorage.setItem('access_token', token);
            
            // Remove o token do hash
            history.replaceState(null, document.title, window.location.pathname + window.location.search);
            
            // Recarrega a página para aplicar o token
            window.location.reload();
        }
    }
}

// Inicialização: atualiza a UI com base no estado de autenticação
document.addEventListener('DOMContentLoaded', async function() {
    console.log('DOM carregado, verificando autenticação...');
    console.log('Página atual:', window.location.pathname);
    console.log('É página pública?', isPublicPage());
    console.log('Token presente?', !!getToken());
    
    // Chama a função de depuração para mostrar o token no console
    logToken();
    
    // Verifica se há token no hash da URL
    checkHashToken();
    
    // Adiciona o middleware para navegações diretas
    addTokenToNavigation();
    
    // Se estamos em uma página pública, não precisamos fazer mais nada
    if (isPublicPage()) {
        console.log('Página pública, não é necessário verificar autenticação');
        updateUI(isAuthenticated());
        
        // Se estamos na página de login mas já estamos autenticados, redireciona para a página inicial
        if (isAuthenticated() && window.location.pathname === '/login') {
            console.log('Autenticado e na página de login, redirecionando...');
            const redirectPath = sessionStorage.getItem('redirect_after_login') || '/';
            sessionStorage.removeItem('redirect_after_login');
            window.location.href = redirectPath;
        }
        return;
    }
    
    // Verifica autenticação com o servidor, mas não redireciona automaticamente
    const isAuth = await checkAuthStatus();
    console.log('checkAuthStatus retornou:', isAuth);
    
    // Adiciona listener para o botão de logout em todas as páginas
    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) {
        console.log('Adicionando listener para botão de logout');
        logoutButton.addEventListener('click', logout);
    }
}); 