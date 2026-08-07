"""
test_fontes.py — testa as chaves de Perplexity e GNews isoladamente.

Uso:  python3 test_fontes.py
Lê o .env, faz UMA chamada real em cada API e mostra o que voltou.
Serve para confirmar que as chaves funcionam antes de depender do app.
"""
import os
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

print("=" * 56)
print("1) PERPLEXITY")
print("=" * 56)
if not os.getenv("PERPLEXITY_API_KEY"):
    print("✗ PERPLEXITY_API_KEY vazia no .env")
else:
    try:
        from tools.perplexity_source import fetch_trends
        r = fetch_trends("Tecnologia e Ciência")
        if r["topics"]:
            print(f"✓ Funcionou! {len(r['topics'])} temas, {len(r['links'])} fontes:")
            for t in r["topics"][:5]:
                print("   •", t)
            for l in r["links"][:3]:
                print("   🔗", l["url"])
        else:
            print("⚠ Conectou mas voltou vazio. Verifique crédito/modelo na conta.")
    except Exception as e:
        print(f"✗ Erro: {type(e).__name__}: {e}")

print()
print("=" * 56)
print("2) NOTÍCIAS (", os.getenv("NEWS_PROVIDER", "gnews"), ")")
print("=" * 56)
if not os.getenv("NEWS_API_KEY"):
    print("✗ NEWS_API_KEY vazia no .env")
else:
    try:
        from tools.news_source import fetch_news
        n = fetch_news("tecnologia")
        if n["headlines"]:
            print(f"✓ Funcionou! {len(n['headlines'])} manchetes:")
            for h in n["headlines"][:5]:
                print(f"   • {h['title']}  ({h['source']})")
        else:
            print("⚠ Conectou mas voltou vazio. Verifique a chave/limite diário.")
    except Exception as e:
        print(f"✗ Erro: {type(e).__name__}: {e}")

print()
print("=" * 56)
print("3) X / TWITTER (", os.getenv("X_PROVIDER", "twitterapi"), ")")
print("=" * 56)
if not os.getenv("X_API_KEY"):
    print("✗ X_API_KEY vazia no .env")
else:
    try:
        from tools.x_source import fetch_x
        # busca o que está bombando sobre tecnologia (min_faves baixo p/ ver resultado)
        x = fetch_x("tecnologia", mode="bombando", min_faves=20)
        if x["topics"]:
            print(f"✓ Funcionou! {len(x['topics'])} tweets em alta:")
            for t in x["topics"][:5]:
                print("   •", t[:90])
        else:
            print("⚠ Conectou mas voltou vazio. Tente baixar X_MIN_FAVES "
                  "(ex: 100) ou confira o crédito da conta.")
    except Exception as e:
        print(f"✗ Erro: {type(e).__name__}: {e}")
