# frente3_web\backend\manage.py
"""
Ponto de entrada do Django da Frente 3.

CMD -> python frente3_web/backend/manage.py migrate      (uma vez)
       python frente3_web/backend/manage.py runserver    (sobe a API)

Roda a partir da raiz do projeto, D:\\Code\\TCC2, como as outras
frentes.
"""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "servidor.settings")

    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()