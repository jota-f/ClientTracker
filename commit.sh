#!/bin/bash
git checkout master
git add app/api/routes/clients.py app/api/routes/tasks.py app/main.py app/models/client.py app/models/task.py app/services/client_service.py app/services/dashboard_service.py app/services/task_service.py app/templates/priority_matrix.html .gitignore
git commit -m "Implementação de permissões por usuário e controle de acesso baseado em propriedade"
echo "Commit concluído com sucesso!" 