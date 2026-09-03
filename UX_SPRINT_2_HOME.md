# UX Sprint 2 — Home

## Objetivo
Transformar a Home em um ponto de decisão orientado à tarefa: primeiro retomar atividade real em andamento; depois escolher entre Aprender, Criar e Encontrar oportunidades.

## Auditoria
- A Home anterior apresentava Georgina, Marcos Cezar e Youtuber como arquitetura primária.
- O bloco de curso em andamento existia, mas aparecia como cartão flutuante secundário.
- O card de audiência levava a `/youtuber`, embora o objetivo definido para a Home seja descobrir oportunidades.
- Já existe `/api/curso-atual`; nenhum progresso fictício foi criado.

## Implementação
- `Continue de onde parou` passa a ocupar a primeira posição quando `/api/curso-atual` retorna um curso.
- Sem curso em andamento, o bloco não é renderizado visualmente e a Home começa diretamente pela nova atividade.
- Três caminhos orientados à tarefa: Aprender (`/curso`), Criar (`/estudio`) e Encontrar oportunidades (`/trends`).
- Personagens preservados como branding secundário.
- Identidade dark/neon, imagens existentes e topbar preservadas.
- Estados de erro do carregamento do curso são silenciosos porque a ausência desse dado não impede a tarefa principal.
- Eventos UX mínimos persistidos: `home_view`, `continue_learning_click`, `learn_click`, `create_click`, `trends_click`.

## Backend requirement
A Home já possuía o backend necessário para continuidade (`/api/curso-atual`). Foi adicionada somente telemetria UX allow-listed em `/api/ux/events`, sem conteúdo livre do usuário.

## Acessibilidade e responsividade
- `focus-visible` explícito.
- Touch targets >= 44px nos CTAs.
- Layout 3 colunas no desktop e empilhado em tablet/mobile.
- `prefers-reduced-motion` desativa transições relevantes.
- Estado e progresso usam texto além da cor.
