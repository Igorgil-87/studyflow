# UX Sprint 1 — Arquitetura da Informação e Navegação

## Auditoria

Estado anterior: a navegação era contextual por personagem/módulo. Em uma página de estudo, por exemplo, o usuário via apenas Georgina; em Youtuber, apenas Youtuber/Trends/RAG. Isso reduzia ruído local, mas escondia a arquitetura global e exigia conhecer os personagens para descobrir capacidades.

Problemas encontrados:
- `Dashboard`, `Georgina`, `Marcos Cezar`, `Youtuber` e `Trends` misturavam destino, personagem e terminologia de produto.
- áreas principais desapareciam conforme o módulo atual;
- `Growth` estava no menu de conta, apesar de ser uma capacidade de produto;
- a arquitetura não expressava diretamente os objetivos Aprender / Criar / Crescer;
- não havia reforço visual discreto de qual área macro estava ativa.

Componentes afetados: sidebar global e cabeçalho móvel. Rotas/APIs: nenhuma rota ou API alterada.

## Solução implementada

A navegação principal agora é persistente e orientada a tarefas:
- Principal → Início
- Aprender → Criar plano de estudo, Cursos, Trilhas, Certificados, Eventos
- Criar → Estúdio de criação
- Crescer → Tendências, Produção de vídeo, Pergunte ao vídeo, Desempenho

Georgina e Marcos Cezar permanecem como branding secundário nos títulos das áreas, sem serem necessários para entender a função. A identidade Youtuber continua dentro da experiência de vídeo, mas não é usada como label primário da navegação.

Recursos técnicos (Observabilidade, Security, AI Gateway, Production Health, Case) continuam no menu de conta/avançado e não competem com tarefas do usuário comum.

## Dependências

FRONTEND ONLY. Nenhuma mudança de backend foi necessária.

## Risco controlado

Nenhuma URL foi renomeada e nenhum contrato backend mudou. `modulo_group` continua aceito pelos templates existentes para evitar regressão, embora a sidebar já não dependa dele para decidir o que mostrar.
