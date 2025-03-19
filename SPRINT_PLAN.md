# ClientTracker - Plano de Sprints

## Sprint 1: Setup & Arquitetura Básica (1 semana) ✅
### Tarefas
- ✅ Configurar repositório, ambiente virtual e estrutura do projeto
- ✅ Configurar FastAPI, criar módulo para instância da aplicação e integrar MongoDB
- ✅ Criar endpoints básicos (health check) e página inicial com Jinja2

### Entregáveis
- ✅ Projeto inicial funcional com FastAPI e conexão MongoDB
- ✅ Página inicial renderizada via Jinja2

## Sprint 2: Módulo de Clientes e Modelo RFM (1-2 semanas) ✅
### Tarefas
- ✅ Implementar operações CRUD para clientes com MongoDB
- ✅ Definir e integrar campos essenciais (Nome, Empresa, etc.)
- ✅ Desenvolver lógica de pontuação RFM e atualizar modelo de cliente
- ✅ Criar dashboard HTML para visualização dos clientes e pontuações

### Entregáveis
- ✅ Módulo de gestão de clientes funcional
- ✅ Cálculo automático do score RFM e dashboard

## Sprint 3: Módulo de Tarefas e Matriz Eisenhower (1-2 semanas) ✅
### Tarefas
- ✅ Modelar e implementar operações CRUD para tarefas
- ✅ Desenvolver interface visual Kanban para gerenciamento
- ✅ Integrar funcionalidades drag-and-drop
- ✅ Permitir associação de tarefas aos clientes

### Entregáveis
- ✅ Sistema de gerenciamento de tarefas estilo Trello
- ✅ Funcionalidades de organização e reordenação

## Sprint 4: Lembretes, Automação e Integrações (1 semana) 🔄
### Tarefas
- ✅ Integrar Google Calendar para agendamento
- ❌ Integrar Outlook para agendamento
- ✅ Configurar sistema de notificações (email)
- ❌ Implementar periodicidade de contato baseada no RFM

### Entregáveis
- 🔄 Sistema de agendamento e notificações parcialmente implementado

## Sprint 5: Relatórios e UI/UX (1 semana)
### Tarefas
- Desenvolver dashboard de indicadores
- Implementar interface para revisão semanal
- Refinar design e garantir responsividade
- Realizar testes de usabilidade

### Entregáveis
- Módulo de relatórios completo
- Interface aprimorada e testada

## Sprint 6: Segurança e Deployment (1 semana) 🔄
### Tarefas
- ✅ Implementar autenticação (adiantado e concluído)
- Implementar MFA
- Garantir criptografia dos dados
- Escrever testes automatizados
- Preparar deployment com Docker
- Realizar deployment em staging

### Entregáveis
- Aplicação segura e testada
- Ambiente de deployment configurado 