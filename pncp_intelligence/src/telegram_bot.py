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
from typing import Any, Dict, List, Optional
import pandas as pd

logger = logging.getLogger("TelegramNotifier")


def parse_datetime_safe(date_val: Any) -> Optional[datetime]:
    """Tenta converter formatos diversos de data para um objeto datetime válido."""
    if not date_val or pd.isna(date_val):
        return None
    s = str(date_val).strip()
    if s in ["Ver Edital", "Não informado", "N/A", "A definir", ""]:
        return None

    # Remove frações de segundos
    s_clean = s.split(".")[0].strip()

    for fmt in [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d.%m.%Y",
    ]:
        try:
            return datetime.strptime(s_clean, fmt)
        except ValueError:
            pass

    if "T" in s_clean:
        try:
            parts = s_clean.split("T")
            d_parts = [int(x) for x in parts[0].split("-")]
            t_parts = [int(x) for x in parts[1][:5].split(":")]
            return datetime(d_parts[0], d_parts[1], d_parts[2], t_parts[0], t_parts[1])
        except Exception:
            pass

    return None


def is_opportunity_expired(date_val: Any) -> bool:
    """Verifica se a oportunidade tem data limite definida e se essa data já expirou."""
    dt = parse_datetime_safe(date_val)
    if dt:
        # Se veio sem hora definida (00:00), considera o final do dia
        if dt.hour == 0 and dt.minute == 0:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt < datetime.now()
    return False


def format_ptbr_date(date_val: Any) -> str:
    """Converte strings de datas ISO para o padrão ABNT / PT-BR (DD/MM/AAAA às HH:MM)."""
    if not date_val or pd.isna(date_val):
        return "Não informado"
    s = str(date_val).strip()
    if s in ["Ver Edital", "Não informado", "N/A", "A definir", ""]:
        return "Ver Edital"

    dt = parse_datetime_safe(s)
    if dt:
        if dt.hour != 0 or dt.minute != 0:
            return dt.strftime("%d/%m/%Y às %H:%M")
        return dt.strftime("%d/%m/%Y")

    if "T" in s:
        parts = s.split("T")
        date_pt = parts[0].split("-")
        if len(date_pt) == 3:
            time_part = parts[1][:5]
            return f"{date_pt[2]}/{date_pt[1]}/{date_pt[0]} às {time_part}"

    return s


def infer_pncp_requirements(subtema: str, modalidade: str, objeto: str) -> str:
    """Infere pré-requisitos técnicos e documentais da licitação com base no objeto e modalidade."""
    subtema_lower = (subtema or "").lower()
    objeto_lower = (objeto or "").lower()

    reqs = ["SICAF/Certidões fiscais regulares", "Atestado de Capacidade Técnica (escopo similar)"]

    if any(k in subtema_lower or k in objeto_lower for k in ["ia", "inteligência artificial", "machine learning", "bi", "business intelligence", "analytics", "dados"]):
        reqs.append("Experiência comprovada em implantação de BI/Analytics ou modelos de IA")
        reqs.append("Garantia de segurança da informação e interoperabilidade de dados")
    elif any(k in subtema_lower or k in objeto_lower for k in ["lgpd", "privacidade", "segurança", "backup"]):
        reqs.append("Conformidade com a LGPD e normas de segurança (ISO/IEC)")
        reqs.append("Atestação de fornecimento de infraestrutura corporativa de backup/armazenamento imutável")
    elif any(k in subtema_lower or k in objeto_lower for k in ["avaliação", "ideb", "saeb", "psicometria", "tri", "educacional"]):
        reqs.append("Comprovação em avaliação educacional de redes ou elaboração de itens/psicometria")
        reqs.append("Equipe técnica multidisciplinar especializada em educação e dados")
    elif any(k in subtema_lower or k in objeto_lower for k in ["gestão escolar", "sige", "emis", "sgp"]):
        reqs.append("Atestado de desenvolvimento/sustentação de software de gestão pedagógica/escolar")
        reqs.append("Capacidade de integração via APIs com ecossistemas governamentais")
    elif any(k in subtema_lower or k in objeto_lower for k in ["consultoria", "assessoria", "estudos"]):
        reqs.append("Atestado de consultoria técnica especializada intelectual para o setor público")
    else:
        reqs.append(f"Atendimento integral às especificações do Edital ({modalidade})")

    return " • ".join(reqs)


def infer_icaro_prereqs(cargo: str, fonte: str, escopo: Optional[str] = None) -> str:
    """Gera pré-requisitos objetivos esperados para contratação em agências/terceiro setor."""
    c_lower = (cargo or "").lower()
    e_lower = (escopo or "").lower()

    reqs = ["Graduação concluída e Pós-graduação/Mestrado na área"]

    if any(k in c_lower or k in e_lower for k in ["dados", "analytics", "ia", "inteligência artificial", "especificação funcional", "requisitos"]):
        reqs.append("Experiência mínima de 4 a 5 anos em análise de dados, arquitetura ou governança de TI pública")
        reqs.append("Domínio de Python/R/SQL, APIs e integração de grandes bases de dados")
    elif any(k in c_lower or k in e_lower for k in ["evasão", "trajetória", "educação", "educacional", "processos", "permanente"]):
        reqs.append("Experiência mínima comprovada em políticas educacionais públicas ou gestão de redes de ensino")
        reqs.append("Vivência prévia em elaboração de planos estratégicos, formação ou cooperação técnica internacional")
    elif any(k in c_lower or k in e_lower for k in ["consultor individual", "consultor sênior", "especialista"]):
        reqs.append("Experiência sólida (5+ anos) comprovada por atestados/produtos entregues em organismos correlatos")
    else:
        reqs.append("Experiência profissional relevante e comprovação técnica curricular compatível")

    return " • ".join(reqs)


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

        # Mantém ambiente sincronizado para submódulos
        if self.token:
            os.environ["TELEGRAM_TOKEN"] = self.token
            os.environ["TELEGRAM_BOT_TOKEN"] = self.token
        if self.chat_id:
            os.environ["TELEGRAM_CHAT_ID"] = self.chat_id

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
        """Envia mensagem de texto via Telegram Bot API com divisão segura por parágrafos."""
        if not self.is_configured:
            logger.warning(
                "Telegram não configurado. Defina TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no seu .env"
            )
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        # Divide mensagens respeitando parágrafos para não quebrar tags HTML
        chunks = []
        current_chunk = ""
        for paragraph in text.split("\n\n"):
            if len(current_chunk) + len(paragraph) + 2 > 3800:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
            else:
                current_chunk += paragraph + "\n\n"
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

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

    def send_integrated_briefing(
        self,
        df_radar: pd.DataFrame,
        icaro_opps: List[Dict[str, Any]],
        top_pncp: int = 6,
        top_icaro: int = 6,
        db: Optional[Any] = None,
        cooldown_days: int = 14,
        filter_notified: bool = True,
    ) -> bool:
        """Dispara um ÚNICO briefing executivo consolidado com as oportunidades do PNCP e do I.C.A.R.O.
        
        Desduplica avisos consultando o banco SQLite para garantir que o usuário não receba
        notificações repetidas dentro da janela de cooldown configurada.
        """
        data_hoje = datetime.now().strftime("%d/%m/%Y às %H:%M")

        # Rastreamento de já notificados
        notificados_pncp = set()
        notificados_icaro = set()
        if db and filter_notified:
            try:
                notificados_pncp = db.obter_codigos_notificados(origem="PNCP", dias_cooldown=cooldown_days)
                notificados_icaro = db.obter_codigos_notificados(origem="ICARO", dias_cooldown=cooldown_days)
            except Exception as e:
                logger.warning(f"Não foi possível recuperar histórico de notificações do banco: {e}")

        # Métricas PNCP
        total_pncp = len(df_radar) if not df_radar.empty else 0
        altos_pncp = int((df_radar["score_candidatura"] >= 75).sum()) if not df_radar.empty else 0
        vol_total = df_radar["valor_total_estimado"].sum() if not df_radar.empty else 0.0

        if vol_total >= 1_000_000_000:
            vol_str = f"R$ {vol_total / 1_000_000_000:,.2f} bi".replace(",", "X").replace(".", ",").replace("X", ".")
        elif vol_total >= 1_000_000:
            vol_str = f"R$ {vol_total / 1_000_000:,.2f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            vol_str = f"R$ {vol_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # Métricas I.C.A.R.O.
        altas_icaro = [o for o in icaro_opps if o.get("score") == "Alta"]
        medias_icaro = [o for o in icaro_opps if o.get("score") == "Média"]

        # Cabeçalho Principal
        lines = [
            "🚀 <b>RADAR INTEGRADO • BRIEFING EXECUTIVO DO DIA</b>",
            f"📅 <i>Consolidado Nacional &amp; Internacional • {data_hoje}</i>",
            "",
            "📊 <b>Panorama Geral:</b>",
            f"• <b>PNCP (Governo):</b> {total_pncp} abertos ({altos_pncp} de Alta Recomendação • {vol_str})",
            f"• <b>I.C.A.R.O. (Agências/Privado):</b> {len(altas_icaro)} Altas Chances, {len(medias_icaro)} Médias Chances",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "🏛️ <b>1. LICITAÇÕES PÚBLICAS &amp; GOVERNO (PNCP)</b>",
            "<i>Editais em aberto com alta aderência técnica e viabilidade logística:</i>",
            ""
        ]

        # 1. Detalhamento PNCP com Desduplicação Inteligente
        itens_para_gravar_pncp = []
        if df_radar.empty or altos_pncp == 0:
            lines.append("<i>ℹ️ Nenhuma nova licitação com Fit Score ≥ 75 aberta hoje.</i>\n")
        else:
            # Separa editais inéditos vs já notificados
            if filter_notified and notificados_pncp and "numero_controle_pncp" in df_radar.columns:
                df_novos = df_radar[~df_radar["numero_controle_pncp"].astype(str).isin(notificados_pncp)]
                if not df_novos.empty:
                    top_df = df_novos.sort_values("score_candidatura", ascending=False).head(top_pncp)
                    qtd_ocultos = len(notificados_pncp.intersection(set(df_radar["numero_controle_pncp"].astype(str))))
                    if qtd_ocultos > 0:
                        lines.append(f"✨ <i>Exibindo {len(top_df)} novas oportunidades ({qtd_ocultos} já notificadas omitidas para evitar duplicatas).</i>\n")
                else:
                    lines.append("<i>ℹ️ Todos os editais com Fit Score ≥ 75 já foram notificados anteriormente no Telegram. Acompanhamento em tempo real no Dashboard.</i>\n")
                    top_df = pd.DataFrame()
            else:
                top_df = df_radar.sort_values("score_candidatura", ascending=False).head(top_pncp)

            for i, (_, row) in enumerate(top_df.iterrows(), 1):
                score = int(row.get("score_candidatura", 0))
                pncp_id = str(row.get("numero_controle_pncp", "")).strip()
                processo = str(row.get("processo", "")).strip()
                orgao = str(row.get("razao_social_orgao", "Órgão Não Informado"))[:45]
                uf = str(row.get("uf_sigla", "BR"))
                modalidade = str(row.get("modalidade_nome", "Pregão"))
                subtema = str(row.get("matched_subtema", "Tecnologia/Educação"))
                dias = float(row.get("dias_restantes", 0.0))
                valor = float(row.get("valor_total_estimado", 0.0))
                url = str(row.get("url_oficial_edital", ""))
                keywords = str(row.get("matched_keywords", "")).strip()
                objeto_raw = str(row.get("objeto_compra", "")).strip()

                # Limpeza e formatação do objeto real com maior detalhamento (até 480 caracteres)
                for prefix in ["[Portal de Compras Públicas] - ", "[LICITANET] - ", "[BLL Compras] - "]:
                    if objeto_raw.startswith(prefix):
                        objeto_raw = objeto_raw[len(prefix):]
                objeto_raw = " ".join(objeto_raw.split())
                if len(objeto_raw) > 480:
                    corte = objeto_raw[:477].rfind(" ")
                    objeto_resumo = objeto_raw[:corte] + "..." if corte > 300 else objeto_raw[:477] + "..."
                else:
                    objeto_resumo = objeto_raw

                # Busca itens/módulos detalhados do lote no banco SQLite se disponível
                itens_resumo = []
                if db and pncp_id:
                    try:
                        with db.get_connection() as conn:
                            cur = conn.cursor()
                            cur.execute(
                                "SELECT numero_item, descricao, quantidade, valor_total_estimado FROM itens_contratacao WHERE numero_controle_pncp = ? ORDER BY numero_item ASC LIMIT 3",
                                (pncp_id,)
                            )
                            it_rows = cur.fetchall()
                            for it in it_rows:
                                d_it = " ".join(str(it["descricao"]).split())
                                if len(d_it) > 85:
                                    d_it = d_it[:82] + "..."
                                itens_resumo.append(f"  • <i>Item {it['numero_item']}:</i> {d_it}")
                    except Exception:
                        pass

                if valor >= 1_000_000:
                    val_str_item = f"R$ {valor / 1_000_000:,.2f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
                elif valor > 0:
                    val_str_item = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                else:
                    val_str_item = "Valor sob demanda"

                # Formatação de data ABNT / PT-BR
                dt_raw = row.get("data_encerramento_proposta") or row.get("data_abertura_proposta")
                dt_abnt = format_ptbr_date(dt_raw)
                if dt_abnt not in ["Não informado", "Ver Edital"]:
                    prazo_desc = f"{dt_abnt} ({dias:.0f}d restantes)" if dias > 0 else dt_abnt
                else:
                    prazo_desc = f"{dias:.0f}d restantes" if dias > 0 else "Ver Edital"

                # Código de Referência Unificado
                ref_text = f"<code>{pncp_id}</code>"
                if processo and processo not in ["None", "nan", ""]:
                    ref_text += f" (Proc. <b>{processo}</b>)"

                # Pré-requisitos objetivos de qualificação técnica e habilitação
                reqs_pncp = infer_pncp_requirements(subtema, modalidade, objeto_raw)

                badge = "🟢" if score >= 75 else "🟡"
                lines.append(f"{badge} <b>[PNCP #{i}] Score {score}/100 • {val_str_item}</b>")
                lines.append(f"🆔 <b>Ref:</b> {ref_text}")
                lines.append(f"🏛️ <b>{orgao} ({uf})</b> • {modalidade}")
                if objeto_resumo:
                    lines.append(f"📦 <b>Objeto Detalhado:</b> {objeto_resumo}")
                if itens_resumo:
                    lines.append("📑 <b>Módulos/Itens:</b>\n" + "\n".join(itens_resumo))
                lines.append(f"📋 <b>Pré-requisitos:</b> {reqs_pncp}")
                lines.append(f"🎯 <b>Linha:</b> {subtema} | ⏳ <b>Prazo:</b> {prazo_desc}")
                if keywords:
                    lines.append(f"🔑 <b>Termos-chave:</b> <code>{keywords}</code>")
                if url:
                    lines.append(f"🔗 <a href='{url}'>Acessar Edital no PNCP</a>")
                lines.append("")

                itens_para_gravar_pncp.append({
                    "codigo_referencia": pncp_id,
                    "titulo": objeto_resumo,
                    "score": score,
                    "valor_estimado": valor,
                    "url": url,
                })

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "🌐 <b>2. AGÊNCIAS INTERNACIONAIS, TERCEIRO SETOR &amp; PRIVADO (I.C.A.R.O.)</b>",
            "<i>Consultorias de alto nível, chamadas e posições estratégicas avaliadas por IA:</i>",
            ""
        ])

        # 2. Detalhamento I.C.A.R.O. com Filtro de Expiração e Pré-requisitos
        itens_para_gravar_icaro = []
        candidatos_icaro = altas_icaro + medias_icaro

        # Filtro estrito de datas: descarta imediatamente chamadas cujo prazo já passou
        candidatos_validos = []
        for opp in candidatos_icaro:
            pz = opp.get("prazo") or opp.get("end_date")
            if is_opportunity_expired(pz):
                continue
            candidatos_validos.append(opp)

        if filter_notified and notificados_icaro:
            top_icaro_list = [o for o in candidatos_validos if str(o.get("id", "")).strip() not in notificados_icaro][:top_icaro]
            qtd_icaro_ocultos = len(candidatos_validos) - len(top_icaro_list)
            if top_icaro_list and qtd_icaro_ocultos > 0:
                lines.append(f"✨ <i>Exibindo {len(top_icaro_list)} novas oportunidades vigentes ({qtd_icaro_ocultos} já notificadas omitidas).</i>\n")
        else:
            top_icaro_list = candidatos_validos[:top_icaro]

        if not top_icaro_list:
            lines.append("<i>ℹ️ Nenhuma nova chamada de alta/média aderência em aberto pendente de notificação hoje.</i>\n")
        else:
            for j, opp in enumerate(top_icaro_list, 1):
                opp_id = str(opp.get("id", f"ICARO-{j}")).strip()
                badge_icaro = "🟢" if opp.get("score") == "Alta" else "🟡"
                cargo = opp.get("cargo", opp.get("titulo", "Oportunidade"))
                fonte = opp.get("fonte_orgao", opp.get("grupo", "Geral")).upper()
                local = opp.get("local", "Remoto")
                prazo_raw = opp.get("prazo", "Ver Edital")
                valor_opp = opp.get("valor", "A definir")
                escopo = opp.get("objeto") or opp.get("escopo")
                url_opp = opp.get("url", "")

                # Extrai Pré-requisitos e Aderência separadamente
                pre_reqs = opp.get("pre_requisitos") or opp.get("requisitos")
                if not pre_reqs or pre_reqs in ["Não informado", "N/A", ""]:
                    pre_reqs = infer_icaro_prereqs(cargo, fonte, escopo)

                aderencia = opp.get("aderencia") or opp.get("reasoning", "")
                if not aderencia:
                    aderencia = "Perfil sênior atende aos requisitos de pós-graduação/mestrado e atuação comprovada em consultorias para o setor público."

                # Análise inteligente de prazo
                dt_obj = parse_datetime_safe(prazo_raw)
                if dt_obj:
                    dias_rest = (dt_obj - datetime.now()).total_seconds() / 86400
                    prazo_fmt = format_ptbr_date(prazo_raw)
                    if dias_rest >= 1:
                        prazo_desc = f"{prazo_fmt} (⏳ {dias_rest:.0f}d restantes)"
                    elif dias_rest > 0:
                        prazo_desc = f"{prazo_fmt} (⏳ Encerra hoje!)"
                    else:
                        prazo_desc = prazo_fmt
                else:
                    prazo_desc = "⚠️ Consultar edital (data limite não informada no resumo)"

                lines.append(f"{badge_icaro} <b>[I.C.A.R.O. #{j}] {cargo}</b>")
                lines.append(f"🆔 <b>Ref:</b> <code>{opp_id}</code> | 🏛️ <b>Fonte:</b> {fonte} | 📍 <b>Local:</b> {local}")
                lines.append(f"💰 <b>Remuneração:</b> {valor_opp} | ⏳ <b>Prazo:</b> {prazo_desc}")
                if escopo and escopo not in ["Não informado", "N/A", "Consultoria especializada ou desenvolvimento de projeto técnico."]:
                    lines.append(f"📦 <b>Escopo:</b> {escopo[:300]}")
                lines.append(f"📋 <b>Pré-requisitos:</b> {pre_reqs}")
                lines.append(f"🎯 <b>Aderência:</b> <i>{aderencia}</i>")
                if url_opp:
                    lines.append(f"🔗 <a href='{url_opp}'>Acessar Chamada / Inscrição</a>")
                lines.append("")

                itens_para_gravar_icaro.append({
                    "codigo_referencia": opp_id,
                    "titulo": cargo,
                    "score": opp.get("score"),
                    "url": url_opp,
                })

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "🧭 <b>Aprofundamento &amp; Tomada de Decisão:</b>",
            "Acesse o Dashboard Interativo para navegar nas abas do PNCP e do I.C.A.R.O.",
        ])

        full_message = "\n".join(lines)
        success = self.send_message(full_message)

        # Se enviado com sucesso e o banco foi fornecido, registra no SQLite para evitar reenvio
        if success and db:
            try:
                for item in itens_para_gravar_pncp:
                    if item["codigo_referencia"]:
                        db.registrar_notificacao(
                            origem="PNCP",
                            codigo_referencia=item["codigo_referencia"],
                            titulo=item["titulo"],
                            score=item["score"],
                            valor_estimado=item["valor_estimado"],
                            url=item["url"],
                        )
                for item in itens_para_gravar_icaro:
                    if item["codigo_referencia"]:
                        db.registrar_notificacao(
                            origem="ICARO",
                            codigo_referencia=item["codigo_referencia"],
                            titulo=item["titulo"],
                            score=item["score"],
                            valor_estimado=0.0,
                            url=item["url"],
                        )
                logger.info(
                    f"💾 Notificações registradas no SQLite com sucesso: "
                    f"{len(itens_para_gravar_pncp)} editais PNCP e {len(itens_para_gravar_icaro)} chamadas I.C.A.R.O."
                )
            except Exception as e:
                logger.error(f"⚠️ Erro ao registrar notificações enviadas no SQLite: {e}")

        return success

    def send_candidacy_alert(
        self,
        df_radar: pd.DataFrame,
        top_n: int = 5,
        total_indexados: int = 0,
        db: Optional[Any] = None,
        cooldown_days: int = 14,
        filter_notified: bool = True,
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

        notificados_pncp = set()
        if db and filter_notified:
            try:
                notificados_pncp = db.obter_codigos_notificados(origem="PNCP", dias_cooldown=cooldown_days)
            except Exception:
                pass

        if filter_notified and notificados_pncp and "numero_controle_pncp" in df_radar.columns:
            df_cand = df_radar[~df_radar["numero_controle_pncp"].astype(str).isin(notificados_pncp)]
            if df_cand.empty:
                df_cand = df_radar
        else:
            df_cand = df_radar

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
            f"🎯 <b>TOP {min(top_n, len(df_cand))} OPORTUNIDADES PARA CANDIDATURA:</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        top_df = df_cand.sort_values("score_candidatura", ascending=False).head(top_n)
        itens_enviados = []

        for i, (_, row) in enumerate(top_df.iterrows(), 1):
            score = int(row.get("score_candidatura", 0))
            pncp_id = str(row.get("numero_controle_pncp", "")).strip()
            processo = str(row.get("processo", "")).strip()
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

            ref_text = f"<code>{pncp_id}</code>"
            if processo and processo not in ["None", "nan", ""]:
                ref_text += f" (Proc. <b>{processo}</b>)"

            objeto_raw = str(row.get("objeto_compra", "")).strip()
            for prefix in ["[Portal de Compras Públicas] - ", "[LICITANET] - ", "[BLL Compras] - "]:
                if objeto_raw.startswith(prefix):
                    objeto_raw = objeto_raw[len(prefix):]
            objeto_raw = " ".join(objeto_raw.split())
            if len(objeto_raw) > 450:
                corte = objeto_raw[:447].rfind(" ")
                objeto_resumo = objeto_raw[:corte] + "..." if corte > 300 else objeto_raw[:447] + "..."
            else:
                objeto_resumo = objeto_raw

            reqs_pncp = infer_pncp_requirements(subtema, modalidade, objeto_raw)

            lines.append(f"{badge} <b>#{i} • Score {score}/100 | {val_item_str}</b>")
            lines.append(f"🆔 <b>Ref:</b> {ref_text}")
            lines.append(f"🏛️ <b>{orgao} ({uf})</b> • {modalidade}")
            if objeto_resumo:
                lines.append(f"📦 <b>Objeto Detalhado:</b> {objeto_resumo}")
            lines.append(f"📋 <b>Pré-requisitos:</b> {reqs_pncp}")
            lines.append(f"⏳ Prazo: <b>{dias:.1f} dias restantes</b>")
            if justificativa:
                lines.append(f"💡 <i>{justificativa}</i>")
            if url:
                lines.append(f"🔗 <a href='{url}'>Acessar Edital no PNCP</a>")
            lines.append("─────────────────────────")

            itens_enviados.append({
                "pncp_id": pncp_id,
                "titulo": str(row.get("objeto_compra", ""))[:200],
                "score": score,
                "valor": valor,
                "url": url
            })

        lines.extend([
            "",
            "🌐 <b>Painel Interativo Completo:</b>",
            "Acesse o Dashboard para análise com mapas e filtros: <code>http://localhost:8501</code>"
        ])

        full_message = "\n".join(lines)
        success = self.send_message(full_message)

        if success and db:
            for item in itens_enviados:
                if item["pncp_id"]:
                    try:
                        db.registrar_notificacao(
                            origem="PNCP",
                            codigo_referencia=item["pncp_id"],
                            titulo=item["titulo"],
                            score=item["score"],
                            valor_estimado=item["valor"],
                            url=item["url"]
                        )
                    except Exception:
                        pass

        return success
