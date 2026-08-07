"""
publish/ — publicação dos cortes no YouTube (YouTube Data API v3).

Camada opcional e desacoplada. As bibliotecas do Google são importadas de forma
tardia (só quando você realmente publica), então o app roda normalmente mesmo
sem elas instaladas.

Princípio de segurança: o upload é uma AÇÃO EXPLÍCITA do usuário (botão
"Publicar"), nunca automática — coerente com o resto da arquitetura, onde
endpoints de escrita são deliberados.
"""
