"""Helpers compartilhados para chamadas da Google Drive API v3."""

from __future__ import annotations


def drive_kwargs() -> dict[str, bool]:
    """Kwargs obrigatórios pra todas as chamadas de Drive API v3
    quando se opera em Shared Drives (não My Drive).

    POR QUÊ: a API v3 do Google Drive trata Shared Drives como contexto
    separado. Sem `supportsAllDrives=True` em chamadas de escrita
    (create/update/delete) e `includeItemsFromAllDrives=True` em chamadas
    de leitura (list/get), as operações falham silenciosamente — não
    retornam erro, apenas resultados vazios ou mudanças não persistidas.
    Esse helper centraliza os kwargs pra evitar repetição e omissão
    acidental em chamadas futuras.

    Referência: https://developers.google.com/drive/api/guides/enable-shareddrives
    """
    return {
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
    }
