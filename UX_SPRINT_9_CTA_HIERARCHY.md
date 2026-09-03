# UX Sprint 9 — CTAs e hierarquia de ações

## Escopo
Padronização semântica dos fluxos já redesenhados: Home, Georgina e Tendências. Nenhuma rota, API ou regra de negócio foi alterada.

## Regra
- `primary`: ação que avança a tarefa principal (Continuar, Criar plano, Analisar, Criar conteúdo, Concluir/Salvar confirmação).
- `secondary`: ação útil que não deve competir com o avanço principal (Ver análise, Indexar URL, Novo/Salvar curso).
- `tertiary`: filtro, cancelamento ou ação de baixa ênfase.

A marcação `data-action-level` torna a hierarquia auditável sem acoplar JavaScript à apresentação. IDs e seletores existentes foram preservados.

## Decisões
Cards da Home continuam sendo destinos inteiros clicáveis; não foram criados botões aninhados. Filtros de Tendências continuam com estado selecionado próprio e são classificados semanticamente como terciários. Ações destrutivas não foram redesenhadas nesta sprint.

## Backend requirements
Nenhum.
