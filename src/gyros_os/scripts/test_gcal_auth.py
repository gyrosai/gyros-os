"""Teste read-only do OAuth Google Calendar (Fatia 3.2).

Lista os próximos 3 eventos da agenda primária do usuário pra validar
que o fluxo OAuth end-to-end funciona:
1. Credencial persistida no banco é carregada e decriptada.
2. Refresh proativo acontece se o token expirou (margem de 60s).
3. Chamada real ao Google Calendar API retorna eventos.

Este script NÃO cria, edita nem deleta nada. Só lê. Se você quiser
criar evento, é Fatia 3.3.

Uso:
    python -m gyros_os.scripts.test_gcal_auth --user-id +5521981354432

Pré-requisitos:
    - Fluxo de autorização já rodado em
      http://localhost:8000/oauth/google/start?user_id=<user_id>
    - .env configurado com OAUTH_TOKEN_ENCRYPTION_KEY,
      GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import structlog

from gyros_os.oauth.providers.google import (
    GoogleCredentialsNotFound,
    get_google_calendar_client,
)
from gyros_os.shared.db import close_pool, get_pool

log = structlog.get_logger("test_gcal_auth")

# Hardcode — YAGNI pra configurar.
_LOCAL_TZ = ZoneInfo("America/Sao_Paulo")

_WEEKDAYS_PT = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
    6: "Domingo",
}

_MONTHS_PT = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}


def _format_event(index: int, event: dict) -> str:
    """Formata um evento do Google Calendar pra linha humana.

    Trata dois casos:
    - Eventos timed: `start.dateTime` + `end.dateTime` (ISO 8601 com
      offset). Convertemos pro fuso local e mostramos HH:MM-HH:MM.
    - Eventos all-day: `start.date` + `end.date` (formato YYYY-MM-DD,
      sem hora). Mostramos "dia inteiro".
    """
    title = event.get("summary") or "(sem título)"
    start = event.get("start", {})
    end = event.get("end", {})

    # All-day event — campo `date` em vez de `dateTime`.
    if "date" in start:
        d = datetime.fromisoformat(start["date"])
        weekday = _WEEKDAYS_PT[d.weekday()]
        month = _MONTHS_PT[d.month]
        return f"{index}. [{weekday} {d.day:02d}/{month} · dia inteiro] {title}"

    # Timed event — `dateTime` já traz offset (ISO 8601).
    start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(_LOCAL_TZ)
    end_dt = datetime.fromisoformat(end["dateTime"]).astimezone(_LOCAL_TZ)
    weekday = _WEEKDAYS_PT[start_dt.weekday()]
    month = _MONTHS_PT[start_dt.month]
    return (
        f"{index}. [{weekday} {start_dt.day:02d}/{month} "
        f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}] {title}"
    )


async def _list_next_events(user_id: str) -> None:
    """Carrega creds, monta client e imprime os próximos 3 eventos."""
    client = await get_google_calendar_client(user_id=user_id)

    now_iso = datetime.now(UTC).isoformat()
    # googleapiclient é síncrono — .execute() bloqueia. Ok pro script.
    # Resource é construído dinamicamente via __getattr__; pyright não
    # enxerga .events(), daí o type: ignore.
    result = (
        client.events()  # type: ignore[attr-defined]
        .list(
            calendarId="primary",
            timeMin=now_iso,
            maxResults=3,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = result.get("items", [])

    if not events:
        print("Nenhum evento futuro encontrado na agenda primária.")
        return

    print(f"\nPróximos {len(events)} eventos:\n")
    for i, event in enumerate(events, start=1):
        print(_format_event(i, event))
    print()


async def _run(user_id: str) -> None:
    await get_pool()
    try:
        await _list_next_events(user_id)
    finally:
        await close_pool()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Testa o OAuth Google Calendar lendo 3 eventos da agenda"
    )
    parser.add_argument(
        "--user-id",
        required=True,
        help="Phone number do usuário (ex: +5521981354432)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(_run(args.user_id))
    except GoogleCredentialsNotFound:
        print(
            f"\nNenhuma credencial para user_id={args.user_id}.\n"
            f"Rode o fluxo de autorização primeiro: abra no navegador\n"
            f"  http://localhost:8000/oauth/google/start"
            f"?user_id={args.user_id}\n"
        )
        sys.exit(1)
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
