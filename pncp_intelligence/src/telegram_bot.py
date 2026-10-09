"""Módulo de Notificação Executiva via Telegram Bot.

Dispara briefings diários, alertas de editais em aberto de alta recomendação
e resumos de inteligência governamental diretamente no Telegram.
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional
import pandas as pd

logger = logging.getLogger("TelegramNotifier")


class TelegramNotifier:
    """Cliente para envio de notificações formatadas via Telegram Bot API."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        # Carrega .env do projeto se existir
        from pathlib import Path
        for p in [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                os.environ[k.strip()] = v.strip().strip("'\"")
                    break
                except Exception:
                    pass

        # Prioriza TELEGRAM_TOKEN (usado no .env local) ou TELEGRAM_BOT_TOKEN
        self.token = token or os.getenv("TELEGRAM_TOKEN", "").strip() or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()

        # Suporte a Streamlit Secrets (quando hospedado online no Streamlit Community Cloud)
        try:
            import streamlit as st
            if not self.token and hasattr(st, "secrets"):
                self.token = st.secrets.get("TELEGRAM_TOKEN", "") or st.secrets.get("TELEGRAM_BOT_TOKEN", "")
            if not self.chat_id and hasattr(st, "secrets"):
                self.chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
        except Exception:
            pass

    @property
    def is_configured(self) -> bool:
        """Verifica se as credenciais do Telegram estão presentes."""
        return bool(self.token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Envia mensagem de texto via Telegram Bot API."""
        if not self.is_configured:
            logger.warning(
                "Telegram não configurado. Defina TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no seu .env"
            )
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        # Divide mensagens que excedem o limite de 4096 caracteres do Telegram
        max_length = 4000
        chunks = [text[i : i + max_length] for i in range(0, len(text), max_length)]

        success = True
        for chunk in chunks:
            payload = {
                "chat_id": self.chat_id,
                "text": chunk,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json", "User-Agent": "PNCP-Bot/1.0"}
                )
                with urllib.request.urlopen(req, timeout=25) as response:
                    if response.status != 200:
                        logger.error(f"Erro Telegram HTTP {response.status}")
                        success = False
            except Exception as e:
                logger.error(f"Falha ao enviar mensagem no Telegram: {e}")
                success = False

        return success

    def send_candidacy_alert(
        self,
        df_radar: pd.DataFrame,
        top_n: int = 5,
        total_indexados: int = 0
    ) -> bool:
        """Formata e envia o Briefing Executivo Diário com as melhores oportunidades em aberto."""
        if df_radar.empty:
            msg = (
                "🏛️ <b>RADAR PNCP: BRIEFING DIÁRIO</b>\n\n"
                "ℹ️ Não foram encontrados editais com prazos abertos nos filtros vigentes hoje."
            )
            return self.send_message(msg)

        data_hoje = datetime.now().strftime("%d/%m/%Y às %H:%M")
        total_abertos = len(df_radar)
        vol_total = df_radar["valor_total_estimado"].sum()
        altos_fit = int((df_radar["score_candidatura"] >= 75).sum())

        # Formatação de Moeda Brasileira
        if vol_total >= 1_000_000_000:
            vol_str = f"R$ {vol_total / 1_000_000_000:,.2f} bi".replace(",", "X").replace(".", ",").replace("X", ".")
        elif vol_total >= 1_000_000:
            vol_str = f"R$ {vol_total / 1_000_000:,.2f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            vol_str = f"R$ {vol_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        lines = [
            "🏛️ <b>RADAR DE COMPRAS PÚBLICAS • PNCP INTELLIGENCE</b>",
            f"📅 <i>Relatório Diário • {data_hoje}</i>",
            "",
            "📊 <b>Panorama do Pipeline Aberto:</b>",
            f"• <b>{total_abertos}</b> oportunidades ativas no radar",
            f"• <b>{vol_str}</b> em disputa em aberto",
            f"• <b>{altos_fit}</b> editais de <b>Alta Recomendação</b> (Score ≥ 75)",
            "",
            f"🎯 <b>TOP {min(top_n, len(df_radar))} OPORTUNIDADES PARA CANDIDATURA:</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        top_df = df_radar.sort_values("score_candidatura", ascending=False).head(top_n)

        for i, (_, row) in enumerate(top_df.iterrows(), 1):
            score = int(row.get("score_candidatura", 0))
            orgao = str(row.get("razao_social_orgao", "Órgão Não Informado"))[:45]
            uf = str(row.get("uf_sigla", "BR"))
            modalidade = str(row.get("modalidade_nome", "Pregão"))
            subtema = str(row.get("matched_subtema", "Tecnologia/Educação"))
            dias = float(row.get("dias_restantes", 0.0))
            valor = float(row.get("valor_total_estimado", 0.0))
            url = str(row.get("url_oficial_edital", ""))
            justificativa = str(row.get("justificativa_candidatura", ""))

            # Moeda item
            if valor >= 1_000_000:
                val_item_str = f"R$ {valor / 1_000_000:,.2f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                val_item_str = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            badge = "🟢" if score >= 75 else ("🟡" if score >= 50 else "⚪")

            lines.append(f"{badge} <b>#{i} • Score {score}/100 | {val_item_str}</b>")
            lines.append(f"🏛️ <b>{orgao} ({uf})</b>")
            lines.append(f"📦 <b>{subtema}</b> • {modalidade}")
            lines.append(f"⏳ Prazo: <b>{dias:.1f} dias restantes</b>")
            if justificativa:
                lines.append(f"💡 <i>{justificativa}</i>")
            if url:
                lines.append(f"🔗 <a href='{url}'>Acessar Edital no PNCP</a>")
            lines.append("─────────────────────────")

        lines.extend([
            "",
            "🌐 <b>Painel Interativo Completo:</b>",
            "Acesse o Dashboard para análise com mapas e filtros: <code>http://localhost:8501</code>"
        ])

        full_message = "\n".join(lines)
        return self.send_message(full_message)
