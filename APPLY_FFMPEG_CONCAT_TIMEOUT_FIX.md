# Fix: timeout ao colar fechamento

O job RQ estava saudável, mas o `append_outro()` matava o FFmpeg após 180 segundos.
Em produção, os renders 1080x1920 chegaram muito perto ou acima desse limite.

## Alterações

- timeout do fechamento configurável via `VIDEO_CONCAT_TIMEOUT_SECONDS`;
- padrão aumentado de 180s para 600s;
- preset padrão do concat alterado de `fast` para `veryfast` para reduzir tempo de CPU;
- `VIDEO_CONCAT_PRESET` permite voltar para `fast` ou outro preset sem alterar código;
- comportamento é idêntico em local e cloud; só o `.env` muda.

## Produção recomendada

```env
VIDEO_CONCAT_TIMEOUT_SECONDS=600
VIDEO_CONCAT_PRESET=veryfast
```

## Local

Pode deixar as variáveis ausentes; os mesmos defaults serão usados.
