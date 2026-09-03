# UX Sprint 3 — Georgina / criação da jornada de estudo

## Auditoria
A tela repetia “Como você quer começar?” e “Escolha sua fonte”, usava “Gerar curso” antes de oferecer revisão e mantinha uma linguagem diferente entre YouTube e Meu material.

## Solução
- Uma pergunta de decisão: “De onde vem o conteúdo?”
- YouTube e Meu material como fontes explícitas.
- Formulário adaptativo: tema apenas no YouTube; upload e personalização apenas em Meu material.
- CTA unificado: “Criar plano de estudo”.
- Preview/revisão reaproveita a tela existente `/curso2/<id>/revisar`.
- No YouTube, o roadmap já produzido pelo pipeline é persistido por `/api/curso2/from-youtube/<job_id>` e aberto para revisão, sem nova chamada ao LLM.
- Em Meu material, `/api/curso2/criar` já cria manifesto em `aguardando_aprovacao` e redireciona para a mesma revisão.

## Classificação
Frontend + reutilização de backend existente. Nenhuma API nova.

## Limitação conhecida
O pipeline YouTube legado ainda executa sua geração existente antes de transformar o roadmap em plano revisável. Separar uma etapa de planejamento mais barata da geração completa exige um endpoint backend específico de planejamento e fica como BACKEND REQUIREMENT futuro, sem inventar comportamento nesta sprint.
