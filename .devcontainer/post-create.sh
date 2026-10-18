#!/usr/bin/env bash
# ============================================================
#  Execute a la creation du conteneur (postCreateCommand).
#  Sorti du devcontainer.json : une vraie logique conditionnelle
#  y serait illisible, et un script se teste.
# ============================================================
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  # Installeur officiel Astral, pas "pip install uv" : uv gere aussi les
  # versions de Python, il n'a rien a faire dans un environnement pip.
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

if [ -f uv.lock ]; then
  # --frozen : n'ecrit JAMAIS le lock. C'est ce qui garantit que deux
  # machines partant du meme uv.lock obtiennent les memes versions.
  # Sans ce drapeau, uv peut resoudre a nouveau et faire diverger les
  # environnements en silence -- exactement ce qu'on cherche a eviter.
  uv sync --frozen
elif [ -f pyproject.toml ]; then
  echo "Pas de uv.lock : premiere resolution. PENSE A COMMITER uv.lock."
  uv sync
elif [ -f requirements.txt ]; then
  uv venv
  uv pip install -r requirements.txt
else
  echo "Aucun fichier de dependances trouve : rien a installer."
  echo "Pour demarrer un projet :  uv init  puis  uv add <paquet>"
fi
