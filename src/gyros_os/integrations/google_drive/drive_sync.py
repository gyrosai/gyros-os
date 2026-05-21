"""Sync idempotente de instrutor do Pipefy → pasta no Google Drive.

Reproduz a lógica do standalone `~/Documents/cimi-automation/pipefy_to_drive.py`
(validado em produção em 06/maio/2026 com 6 cards reais), com 3 ajustes
deliberados:

1. **Foto via update content (não delete + create):** o standalone faz
   `delete + create` da foto, mas a conta `+5521981354432` não tem
   permissão de delete/trash no Shared Drive `0AMWOAOVQ2sFvUk9PVA`
   (`canDelete=False, canTrash=False`). O Drive API mascara isso como
   404 — daí o "ruído em 100% dos cards" do standalone, e o efeito
   colateral de fotos acumulando na pasta sem ninguém perceber.

   Aqui usamos `update(media_body=)` em arquivo existente que case com
   `name contains 'foto_<slug>'`. Idempotente sem precisar de delete.
   Se a extensão da nova foto difere da antiga, o mesmo `update()`
   também faz rename via `body={"name": ...}`. Ver tech debt.

2. **In-memory uploads:** usa `MediaInMemoryUpload` em vez de
   `MediaFileUpload` — não toca em `/tmp`, sem cleanup necessário,
   mais seguro em ambiente containerizado.

3. **Async wrappers:** `googleapiclient` é síncrono; envolvemos toda
   chamada em `asyncio.to_thread` pra não bloquear o event loop do
   worker.

Idempotência é requisito: rodar duas vezes seguidas pro mesmo card NÃO
cria pasta nova, NÃO duplica `informacoes.md` e NÃO duplica a foto.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import UTC, datetime

import httpx
import structlog
from googleapiclient.http import MediaInMemoryUpload
from pydantic import BaseModel

from gyros_os.integrations.google_drive.helpers import drive_kwargs
from gyros_os.integrations.pipefy.instructor import InstructorInfo

logger = structlog.get_logger()


_CONTENT_TYPE_TO_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}


class SyncResult(BaseModel):
    """Resultado de `sync_instructor_to_drive`.

    Suficientemente rico pra ser serializado direto como `result` JSON
    em `event_queue` (o handler da Fatia 5.2 retorna isto).

    `photo_action` é o audit trail de o que aconteceu com a foto:
    - "created":  arquivo `foto_<slug>.<ext>` não existia, criamos.
    - "updated":  já existia com mesmo nome, sobrescrevemos conteúdo.
    - "renamed":  já existia com extensão diferente; sobrescrevemos
                  conteúdo E renomeamos pra refletir o novo content-type.
    - "skipped":  card sem `foto_url` no Pipefy; nada feito.
    """

    folder_id: str
    folder_url: str
    folder_existed: bool
    photo_action: str  # created | updated | renamed | skipped
    photo_file_id: str | None = None
    photo_size_bytes: int = 0
    informacoes_file_id: str
    informacoes_created: bool


# ---------- Helpers puros ----------


def _normalize_folder_name(nome: str) -> str:
    """UPPERCASE + colapsa whitespace. Garante que `Ana  Maria` e
    `ana maria` viram a mesma pasta `ANA MARIA`."""
    return re.sub(r"\s+", " ", (nome or "").upper()).strip()


def _slugify(value: str) -> str:
    """Lowercase + underscore + ASCII-only. Usado em nomes de arquivo
    (`foto_<slug>.<ext>`). Fallback `instrutor` pra evitar nome vazio."""
    s = re.sub(r"\s+", "_", (value or "").strip().lower())
    s = re.sub(r"[^a-z0-9_\-]", "", s)
    return s or "instrutor"


def _escape_q(value: str) -> str:
    """Escape pra Drive query string (campo `q=`).

    Aspas simples e backslash são os dois caracteres que quebram a query.
    Sem isso, um nome com apóstrofo (`D'Avila`) fecharia a string e
    quebraria a syntax do filtro.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _detect_extension(content_type: str | None, url: str) -> str:
    """Decide extensão do arquivo de foto.

    Prioridade: Content-Type do HTTP > extensão na URL > fallback `jpg`.
    Pipefy serve fotos via signed URL S3 que costuma ter a extensão no
    path antes da query string.
    """
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in _CONTENT_TYPE_TO_EXT:
            return _CONTENT_TYPE_TO_EXT[ct]
    url_clean = url.split("?", 1)[0]
    m = re.search(r"\.([a-zA-Z0-9]{2,5})$", url_clean)
    if m:
        ext = m.group(1).lower()
        if ext in {"jpg", "jpeg", "png", "gif", "webp", "heic", "heif"}:
            return "jpeg" if ext == "jpeg" else ext
    return "jpg"


def _render_informacoes_md(info: InstructorInfo) -> str:
    """Template fixo do `informacoes.md` consumido pela Aimée (marketing).

    POR QUÊ ordem/labels/traços travados: a Aimée tem uma rotina manual
    de leitura desse arquivo pra montar o material de divulgação. Mudar
    a ordem das seções, label ("Cargo" → "Função"), ou separador (`/`
    em Cidade/UF) quebra o consumo dela. Toda mudança aqui precisa
    passar por ela antes.

    Timestamp é local timezone com offset (não UTC puro) — espelha o
    standalone validado em prod.
    """
    nome = info.nome or "(sem nome)"

    cidade_uf_parts = [p for p in [info.cidade, info.uf] if p]
    cidade_uf = "/".join(cidade_uf_parts) or "—"

    categorias = " | ".join(info.categoria_oficina) if info.categoria_oficina else "—"
    tema = info.tema_oficina or "—"
    tema_outro = info.tema_outro or "—"
    minibio = info.minibio or "—"

    now_iso = datetime.now(UTC).astimezone().isoformat(timespec="seconds")

    return (
        f"# {nome}\n\n"
        "**Identificação**\n"
        f"- Cargo: {info.cargo or '—'}\n"
        f"- Empresa: {info.empresa or '—'}\n"
        f"- Cidade/UF: {cidade_uf}\n"
        f"- Telefone: {info.telefone or '—'}\n"
        f"- E-mail: {info.email or '—'}\n\n"
        "**Online**\n"
        f"- LinkedIn: {info.linkedin or '—'}\n"
        f"- Instagram: {info.instagram or '—'}\n\n"
        "**Oficina proposta**\n"
        f"- Categorias: {categorias}\n"
        f"- Tema principal: {tema}\n"
        f"- Tema \"outros\": {tema_outro}\n\n"
        "**Minibio**\n"
        f"{minibio}\n\n"
        "---\n"
        f"_Gerado automaticamente em {now_iso} pela Gyros AI._\n"
    )


# ---------- Helpers Drive (async wrappers em I/O síncrono) ----------


async def _find_or_create_folder(
    drive_service,
    parent_id: str,
    name_normalized: str,
) -> tuple[str, str, bool]:
    """Encontra ou cria a pasta do instrutor sob `parent_id`.

    Retorna `(folder_id, folder_url, existed)`. Idempotência: o filtro
    bate `name = '<normalized>'` exato dentro do parent — dois cards com
    o mesmo nome normalizado caem na mesma pasta (caso conhecido em
    produção; é o comportamento desejado).
    """
    name_q = _escape_q(name_normalized)
    parent_q = _escape_q(parent_id)
    q = (
        f"'{parent_q}' in parents "
        f"and name = '{name_q}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )

    resp = await asyncio.to_thread(
        lambda: drive_service.files().list(
            q=q,
            fields="files(id, name, webViewLink)",
            pageSize=10,
            **drive_kwargs(),
        ).execute()
    )
    files = resp.get("files", [])
    if files:
        f = files[0]
        return (
            f["id"],
            f.get("webViewLink", f"https://drive.google.com/drive/folders/{f['id']}"),
            True,
        )

    body = {
        "name": name_normalized,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = await asyncio.to_thread(
        lambda: drive_service.files().create(
            body=body,
            fields="id, webViewLink",
            supportsAllDrives=True,
        ).execute()
    )
    return (
        created["id"],
        created.get(
            "webViewLink", f"https://drive.google.com/drive/folders/{created['id']}"
        ),
        False,
    )


async def _upload_photo(
    drive_service,
    folder_id: str,
    photo_url: str,
    slug: str,
) -> tuple[str, str | None, int, str | None]:
    """Sincroniza a foto do instrutor na pasta — idempotente sem delete.

    Estratégia: list por prefix `foto_<slug>` na pasta. Se existir
    arquivo, fazemos `update(media_body=)` (e rename, se a extensão
    mudou). Se não existir, criamos. Nunca deletamos — a conta dela
    não tem permissão (ver docstring do módulo).

    Retorna `(action, file_id, size_bytes, extension)`:
    - action="skipped": photo_url vazio. extension=None.
    - action="created": criou novo arquivo `foto_<slug>.<ext>`.
    - action="updated": atualizou conteúdo de arquivo existente, mesmo nome.
    - action="renamed": atualizou conteúdo + renomeou (extensão mudou).

    `extension` reflete a extensão **real** decidida a partir do
    Content-Type da foto baixada (não a extensão da URL do Pipefy);
    nas operações de update/rename, é também a extensão final do
    arquivo no Drive depois da operação.

    NUNCA loga `photo_url`: signed URL do Pipefy contém token de acesso.
    """
    if not photo_url:
        return "skipped", None, 0, None

    async with httpx.AsyncClient() as http:
        r = await http.get(photo_url, timeout=30, follow_redirects=True)
        r.raise_for_status()

    content_type = (
        r.headers.get("Content-Type", "").split(";")[0].strip().lower()
        or "image/jpeg"
    )
    ext = _detect_extension(content_type, photo_url)
    desired_name = f"foto_{slug}.{ext}"
    size = len(r.content)

    folder_q = _escape_q(folder_id)
    prefix_q = _escape_q(f"foto_{slug}")
    existing = await asyncio.to_thread(
        lambda: drive_service.files().list(
            q=(
                f"'{folder_q}' in parents "
                f"and name contains '{prefix_q}' "
                f"and trashed = false"
            ),
            # orderBy="createdTime" garante seleção determinística quando
            # há múltiplos matches (ex: fotos órfãs pré-existentes na
            # pasta da Ana Tedoldi). Sempre escolhemos a mais antiga,
            # então execuções subsequentes batem no mesmo file_id.
            orderBy="createdTime",
            fields="files(id, name)",
            pageSize=10,
            **drive_kwargs(),
        ).execute()
    )
    files = existing.get("files", [])

    media = MediaInMemoryUpload(
        r.content, mimetype=content_type, resumable=True
    )

    if files:
        target = files[0]
        target_id = target["id"]
        target_name = target["name"]

        if target_name == desired_name:
            await asyncio.to_thread(
                lambda: drive_service.files().update(
                    fileId=target_id,
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True,
                ).execute()
            )
            return "updated", target_id, size, ext

        # Extensão mudou (raro: pessoa trocou jpg → png entre execuções).
        # update aceita body+media_body na mesma call — atualiza nome e
        # conteúdo numa transação só.
        await asyncio.to_thread(
            lambda: drive_service.files().update(
                fileId=target_id,
                body={"name": desired_name},
                media_body=media,
                fields="id, name",
                supportsAllDrives=True,
            ).execute()
        )
        return "renamed", target_id, size, ext

    created = await asyncio.to_thread(
        lambda: drive_service.files().create(
            body={"name": desired_name, "parents": [folder_id]},
            media_body=media,
            fields="id, webViewLink",
            supportsAllDrives=True,
        ).execute()
    )
    return "created", created["id"], size, ext


async def _upsert_informacoes_md(
    drive_service,
    folder_id: str,
    info: InstructorInfo,
) -> tuple[str, bool]:
    """Cria ou atualiza `informacoes.md` na pasta. Retorna `(file_id, created)`.

    `created=True` se criou novo, `False` se atualizou existente. A
    sequência (list → update OR create) garante 1 e somente 1 arquivo
    `informacoes.md` por pasta.
    """
    folder_q = _escape_q(folder_id)
    name = "informacoes.md"
    name_q = _escape_q(name)

    existing = await asyncio.to_thread(
        lambda: drive_service.files().list(
            q=f"'{folder_q}' in parents and name = '{name_q}' and trashed = false",
            fields="files(id, name)",
            pageSize=5,
            **drive_kwargs(),
        ).execute()
    )

    content = _render_informacoes_md(info).encode("utf-8")
    media = MediaInMemoryUpload(
        content, mimetype="text/markdown", resumable=False
    )

    files = existing.get("files", [])
    if files:
        file_id = files[0]["id"]
        await asyncio.to_thread(
            lambda: drive_service.files().update(
                fileId=file_id,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            ).execute()
        )
        return file_id, False

    created = await asyncio.to_thread(
        lambda: drive_service.files().create(
            body={"name": name, "parents": [folder_id], "mimeType": "text/markdown"},
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        ).execute()
    )
    return created["id"], True


# ---------- API pública ----------


async def sync_instructor_to_drive(
    info: InstructorInfo,
    drive_service,
    parent_folder_id: str,
) -> SyncResult:
    """Cria ou atualiza pasta de instrutor no Drive, idempotente.

    Sequência de operações:
    1. Encontra ou cria pasta `<NOME NORMALIZADO>` sob `parent_folder_id`.
    2. Sincroniza foto: update se existir `foto_<slug>.*`, create se não
       (nunca delete — conta não tem permissão).
    3. Cria ou atualiza `informacoes.md` (única por pasta).

    POR QUÊ idempotente: o handler que chama essa função pode ser
    invocado várias vezes pro mesmo card (retry de evento, webhook
    duplicado, reprocessamento manual). Operação não-idempotente
    geraria pastas/fotos/informacoes duplicadas no Drive.
    """
    start = time.monotonic()

    # Defesa: sem nome nem título, criaríamos pasta com nome vazio no
    # Drive — efetivamente impossível de achar e fácil de duplicar
    # silenciosamente. Falha rápido antes de tocar no Drive.
    if not (info.nome or info.card_title):
        raise ValueError(
            f"Card {info.card_id} sem nome nem título — "
            f"não dá pra sincronizar"
        )

    logger.info(
        "drive_sync_started",
        card_id=info.card_id,
        instructor_name=info.nome,
    )

    folder_name = _normalize_folder_name(info.nome or info.card_title)
    slug = _slugify(info.nome or info.card_id)

    folder_id, folder_url, existed = await _find_or_create_folder(
        drive_service, parent_folder_id, folder_name
    )
    logger.info(
        "folder_resolved",
        card_id=info.card_id,
        folder_id=folder_id,
        existed=existed,
    )

    photo_action, photo_file_id, photo_size, photo_ext = await _upload_photo(
        drive_service, folder_id, info.foto_url, slug
    )
    logger.info(
        "photo_synced",
        card_id=info.card_id,
        photo_action=photo_action,
        photo_file_id=photo_file_id,
        size_bytes=photo_size,
        extension=photo_ext,
    )

    informacoes_file_id, info_created = await _upsert_informacoes_md(
        drive_service, folder_id, info
    )
    logger.info(
        "informacoes_upserted",
        card_id=info.card_id,
        file_id=informacoes_file_id,
        created=info_created,
    )

    result = SyncResult(
        folder_id=folder_id,
        folder_url=folder_url,
        folder_existed=existed,
        photo_action=photo_action,
        photo_file_id=photo_file_id,
        photo_size_bytes=photo_size,
        informacoes_file_id=informacoes_file_id,
        informacoes_created=info_created,
    )

    latency_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "drive_sync_completed",
        card_id=info.card_id,
        latency_ms=latency_ms,
        photo_action=photo_action,
        result=result.model_dump(),
    )

    return result
