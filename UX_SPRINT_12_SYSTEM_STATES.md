# UX Sprint 12 — Estados do sistema

Padroniza feedback de processamento e erro nos fluxos UX já redesenhados, sem alterar contratos de backend.

## Implementado
- Tendências: estado de processamento com `aria-busy`, erro estruturado e retry real usando a mesma ação existente.
- Georgina: erros inline passam a compartilhar semântica visual de estado.
- Estados não inventam progresso percentual nem sucesso quando o backend não confirma.

## Backend requirement
Nenhum para esta sprint. Estados de indisponibilidade específicos por dependência exigiriam códigos de erro estruturados caso se queira diferenciá-los no futuro.
