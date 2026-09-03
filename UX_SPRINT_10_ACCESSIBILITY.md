# UX Sprint 10 — Acessibilidade

Escopo: Home, Georgina/Curso, Tendências e navegação compartilhada já redesenhados.

## Implementado
- Link “Pular para o conteúdo principal” nas três jornadas.
- Foco global `:focus-visible` de alto contraste, sem depender apenas de hover.
- Navegação ativa expõe `aria-current="page"`.
- Filtros de Tendências expõem estado real via `aria-pressed` e também usam ✓, evitando depender só de cor.
- Drawer de análise mantém dialog, foco inicial, Escape, focus trap e retorno de foco; agora também expõe descrição associada.
- Erros de material/curso usam regiões de alerta.
- Campo de URL de material ganhou label acessível.
- CTAs principais explicitam `type="button"` onde necessário e setas decorativas ficam ocultas de leitores de tela.
- Alvos mínimos de 44px para dispositivos de toque nos controles principais.
- `prefers-reduced-motion` reduz animações/transições.
- Estados disabled recebem feedback visual consistente.

## Limite desta sprint
Não foi feita certificação WCAG automatizada/browser-level nem auditoria com leitor de tela real no ambiente. A sprint melhora a implementação sem alegar conformidade WCAG formal.
