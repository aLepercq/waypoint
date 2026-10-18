# ============================================================
#  Template devcontainer -- Python
#
#  Cette couche existe pour UNE raison : les images devcontainer de
#  Microsoft embarquent un depot apt Yarn (/etc/apt/sources.list.d/
#  yarn.list) dont la cle GPG n'est plus valide.
#
#      NO_PUBKEY 62D54FD4003F6525
#      E: The repository 'https://dl.yarnpkg.com/debian stable
#         InRelease' is not signed.
#
#  Consequence : TOUT apt-get update echoue dans l'image, donc toute
#  feature devcontainer qui installe un paquet meurt en exit 100 --
#  avant meme que le conteneur n'existe. Yarn ne sert a rien ici.
#
#  Corriger dans une couche Dockerfile plutot que dans un
#  postCreateCommand est indispensable : les features s'executent
#  APRES le build de l'image mais AVANT tout hook du cycle de vie.
# ============================================================
ARG BASE=mcr.microsoft.com/devcontainers/python:1-3.12-bookworm
FROM ${BASE}

RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update \
    && rm -rf /var/lib/apt/lists/*

# Pre-create ~/.claude so the named volume inherits vscode ownership
RUN mkdir -p /home/vscode/.claude && chown vscode:vscode /home/vscode/.claude

# Claude Code CLI, installed for vscode so it survives rebuilds
USER vscode
RUN curl -fsSL https://claude.ai/install.sh | bash
USER root
ENV PATH="/home/vscode/.local/bin:${PATH}"
