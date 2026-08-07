"""
test_smtp.py — testa se o envio de e-mail (SMTP) está funcionando.

Como usar:
  1. Preencha SMTP_* no .env (veja OAUTH_LOGIN_SETUP / instruções de MFA).
  2. Rode:  python3 test_smtp.py  seu_destino@email.com
     (se omitir o destino, envia para o próprio SMTP_USER)

Ele NÃO depende do app — serve para isolar o problema de e-mail do resto.
"""

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

# carrega o .env se houver python-dotenv; senão, lê variáveis já exportadas
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

HOST = os.getenv("SMTP_HOST")
PORT = int(os.getenv("SMTP_PORT", "587"))
USER = os.getenv("SMTP_USER")
PASS = os.getenv("SMTP_PASS")
FROM = os.getenv("SMTP_FROM", USER or "")


def main():
    if not HOST:
        print("✗ SMTP_HOST vazio. Preencha o .env primeiro.")
        sys.exit(1)
    if not USER or not PASS:
        print("✗ SMTP_USER ou SMTP_PASS vazio. No Gmail, use uma SENHA DE APP "
              "(16 letras), não a senha normal.")
        sys.exit(1)

    to = sys.argv[1] if len(sys.argv) > 1 else USER
    print(f"→ Servidor : {HOST}:{PORT}")
    print(f"→ De       : {FROM}")
    print(f"→ Para     : {to}")
    print("→ Conectando e enviando...\n")

    msg = EmailMessage()
    msg["Subject"] = "Teste SMTP - StudyFlow"
    msg["From"] = FROM
    msg["To"] = to
    msg.set_content("Funcionou! Se voce recebeu este e-mail, o SMTP do StudyFlow "
                    "esta configurado corretamente e o MFA vai enviar os codigos.",
                    charset="utf-8")

    try:
        ctx = ssl.create_default_context()
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
            print(f"→ Certificados: certifi ({certifi.where()})\n")
        except Exception:
            print("→ Certificados: padrão do sistema "
                  "(se falhar SSL, rode 'Install Certificates.command')\n")
        with smtplib.SMTP(HOST, PORT, timeout=15) as s:
            s.starttls(context=ctx)
            s.login(USER, PASS)
            s.send_message(msg)
        print("✓ E-mail enviado! Confira a caixa de entrada (e o spam).")
    except smtplib.SMTPAuthenticationError:
        print("✗ Falha de autenticação. No Gmail isso quase sempre é:")
        print("  - você usou a senha normal em vez da SENHA DE APP, ou")
        print("  - a verificação em duas etapas não está ativa na conta Google.")
    except ssl.SSLError as e:
        print(f"✗ Erro de certificado SSL: {e}")
        print("  No Mac: rode o 'Install Certificates.command' do seu Python,")
        print("  ou instale o certifi:  pip install certifi")
    except Exception as e:
        print(f"✗ Erro: {type(e).__name__}: {e}")
        print("  Dica: confira HOST/PORT (Gmail = smtp.gmail.com:587) e a rede.")


if __name__ == "__main__":
    main()
