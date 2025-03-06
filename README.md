# ClientTracker

ClientTracker é uma plataforma web-based para gerenciamento e acompanhamento de clientes, integrando funcionalidades de CRM, priorização baseada em modelo RFM adaptado e gestão de tarefas com a Matriz Eisenhower.

## Características Principais

- Gestão completa de clientes com modelo RFM adaptado
- Sistema de tarefas baseado na Matriz Eisenhower
- Interface moderna e minimalista inspirada no Trello
- Automação de follow-ups e notificações
- Relatórios e dashboards intuitivos

## Stack Tecnológica

- **Backend**: FastAPI + Python
- **Frontend**: Jinja2 Templates + HTML/CSS/JS
- **Banco de Dados**: MongoDB
- **Integrações**: Google Calendar, Email/SMS

## Requisitos

- Python 3.8+
- MongoDB
- Ambiente virtual Python (recomendado)

## Configuração do Ambiente

1. Clone o repositório:
```bash
git clone [URL_DO_REPOSITORIO]
cd clienttracker
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:
```env
MONGODB_URL=mongodb://ordos:Mon2tHv8mKg@pgs.app.br:27017/clienttracker?authSource=admin
SECRET_KEY=[sua_chave_secreta]
ENVIRONMENT=development
```

5. Execute a aplicação:
```bash
uvicorn app.main:app --reload
```

A aplicação estará disponível em `http://localhost:8000`

## Estrutura do Projeto

```
clienttracker/
├── app/
│   ├── api/            # Endpoints da API
│   ├── core/           # Configurações centrais
│   ├── db/             # Conexão com banco de dados
│   ├── models/         # Modelos de dados
│   ├── services/       # Lógica de negócios
│   ├── templates/      # Templates Jinja2
│   └── static/         # Arquivos estáticos
├── tests/              # Testes automatizados
├── requirements.txt    # Dependências
└── README.md          # Este arquivo
```

## Desenvolvimento

O projeto está sendo desenvolvido em sprints iterativos. Consulte `SPRINT_PLAN.md` para mais detalhes sobre o planejamento e progresso.

## Licença

Este projeto é proprietário e confidencial. 