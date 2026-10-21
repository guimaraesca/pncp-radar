"""
I.C.A.R.O. — Notificador Executivo e Gerador de Briefings
===========================================================
Formata relatórios e briefings em estilo executivo puro, sem figuras
ou emojis/emoticons. Aplica destaque [URGENTE] em código monospaçado
(fundo âmbar/amarelo) para prazos próximos (<= 5 dias).
Gera relatórios em Markdown, HTML e PDF (PyMuPDF).
"""

import os
import re
import requests
from datetime import datetime, date
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)


def escape_html(text):
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def check_urgency(prazo_str):
    """
    Retorna True se o prazo estiver a menos de ou igual a 5 dias da data de hoje.
    """
    if not prazo_str or not isinstance(prazo_str, str):
        return False
        
    s = prazo_str.strip().split("T")[0].split(" ")[0]
    today = date.today()
    
    for fmt in ["%Y-%m-%d", "%d/%m/%Y"]:
        try:
            d = datetime.strptime(s, fmt).date()
            diff = (d - today).days
            if 0 <= diff <= 5:
                return True
        except ValueError:
            pass
            
    return False


def send_telegram_message(message):
    """
    Envia mensagem formatada em HTML para o canal/chat do Telegram.
    Divide em blocos de até 3800 caracteres respeitando parágrafos.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if token:
        token = token.strip()
    if chat_id:
        chat_id = chat_id.strip()

    if not token or not chat_id or token == "seu_token_aqui":
        print("Aviso: Configuração do Telegram ausente (.env).")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    chunks = []
    current_chunk = ""
    for paragraph in message.split("\n\n"):
        if len(current_chunk) + len(paragraph) + 2 > 3800:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n\n"
        else:
            current_chunk += paragraph + "\n\n"
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    success = True
    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
        except Exception as e:
            print(f"Falha ao enviar mensagem no Telegram: {e}")
            success = False

    return success


def save_report_to_file(report, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Relatório salvo localmente em: {filepath}")


def _format_opportunity_card(r, badge=""):
    """Formata card executivo puro, sem figuras ou emojis."""
    card = ""
    prazo = r.get("prazo", "Não informado")
    is_urgent = check_urgency(prazo)
    
    # Tag de urgência em destaque amarelo/monospaçado (code block no Telegram)
    urgencia_tag = " <code>[URGENTE]</code>" if is_urgent else ""
    
    if badge:
        card += f"<b>{badge}</b>\n"
    card += f"<b>{escape_html(r['title'])}</b>{urgencia_tag}\n"
    
    cargo = r.get("cargo", "Não informado")
    if cargo and cargo not in ["Não informado", "Nao informado", "N/A"]:
        card += f"<b>Cargo:</b> {escape_html(cargo)}\n"
        
    local = r.get("local", "Não informado")
    geo_badge = r.get("geo_badge", "")
    if not geo_badge and isinstance(r.get("geo_info"), dict):
        geo_badge = r["geo_info"].get("badge", "")
    local_str = f"{local} {geo_badge}".strip() if geo_badge else local

    contrato = r.get("contrato", "Não informado")
    card += f"<b>Local:</b> {escape_html(local_str)} | <b>Contrato:</b> {escape_html(contrato)}\n"
    
    valor = r.get("valor", "Não informado")
    card += f"<b>Remuneração / Valor:</b> {escape_html(valor)} | <b>Prazo:</b> {escape_html(prazo)}{urgencia_tag}\n"
    
    objeto = r.get("objeto", "")
    if objeto and objeto not in ["Não informado", "Nao informado", "N/A"]:
        card += f"<b>Escopo:</b> {escape_html(objeto)}\n"
        
    reasoning = r.get("reasoning", "")
    if reasoning:
        card += f"<b>Aderência:</b> {escape_html(reasoning)}\n"
        
    url = r.get("url")
    if url:
        clean_url = escape_html(url)
        card += f"<b>Link:</b> <a href=\"{clean_url}\">Acessar Edital / Inscrição</a>\n\n"
    else:
        card += "\n"
        
    return card


def build_daily_report(results, grupo="todos", version_str="v1"):
    """
    Constrói o relatório do grupo em formato executivo sóbrio.
    Oculta lista detalhada de baixas se não houver altas ou médias.
    """
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    if not results:
        return (
            f"<b>RESUMO I.C.A.R.O. — {grupo.upper()} ({now_str} - {version_str})</b>\n\n"
            f"Nenhum edital novo publicado nesta rodada."
        )

    high_chances = [r for r in results if r.get("score") == "Alta"]
    medium_chances = [r for r in results if r.get("score") == "Média"]
    low_chances = [r for r in results if r.get("score", "") not in ["Alta", "Média"]]

    # Resumo Quantitativo
    report = f"<b>RESUMO I.C.A.R.O. — {grupo.upper()} ({now_str} - {version_str})</b>\n\n"
    report += f"Total Analisado: {len(results)}\n"
    report += f"Altas Chances: {len(high_chances)} | Médias: {len(medium_chances)} | Baixas/Outras: {len(low_chances)}\n\n"
    report += "----------------------------------------\n\n"

    # Se não houver nem Alta nem Média, encerra com mensagem limpa e executiva
    if not high_chances and not medium_chances:
        report += (
            f"<i>Nenhuma oportunidade de alta ou média aderência identificada nesta rodada.\n"
            f"({len(low_chances)} editais avaliados e descartados por baixa convergência com o perfil).</i>\n"
        )
        return report

    # Detalhamento Altas Chances
    if high_chances:
        report += "<b>VAGAS COM ALTAS CHANCES</b>\n\n"
        for r in high_chances:
            report += _format_opportunity_card(r)

    # Detalhamento Médias Chances
    if medium_chances:
        report += "<b>VAGAS COM MÉDIAS CHANCES</b>\n\n"
        for r in medium_chances:
            report += _format_opportunity_card(r)

    # Nota compacta sobre as baixas chances
    if low_chances:
        report += f"<i>(Outras {len(low_chances)} vagas analisadas apresentaram baixa aderência técnica e foram descartadas).</i>\n"

    return report


def build_consolidated_briefing(all_results_by_group):
    """
    Constrói o Briefing Executivo Consolidado do Dia reunindo
    as melhores oportunidades de todos os grupos em estilo sóbrio.
    """
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    all_high = []
    all_medium = []
    group_summary_lines = []
    
    for grp, res in all_results_by_group.items():
        high = [r for r in res if r.get("score") == "Alta"]
        med = [r for r in res if r.get("score") == "Média"]
        all_high.extend(high)
        all_medium.extend(med)
        group_summary_lines.append(f"- <b>{grp.upper()}</b>: {len(high)} Altas, {len(med)} Médias ({len(res)} analisadas)")

    report = f"<b>I.C.A.R.O. — BRIEFING EXECUTIVO CONSOLIDADO</b>\n"
    report += f"Data: {now_str}\n\n"
    report += f"<b>Panorama do Monitoramento:</b>\n"
    report += "\n".join(group_summary_lines) + "\n\n"
    report += f"<b>Total de Destaques:</b> {len(all_high)} Altas | {len(all_medium)} Médias\n"
    report += "----------------------------------------\n\n"

    if all_high:
        report += "<b>DESTAQUES DE ALTA ADERÊNCIA</b>\n\n"
        for idx, r in enumerate(all_high, 1):
            prazo = r.get("prazo", "Não informado")
            is_urgent = check_urgency(prazo)
            urg_tag = " <code>[URGENTE]</code>" if is_urgent else ""
            
            report += f"<b>{idx}. {escape_html(r['title'])}</b>{urg_tag}\n"
            cargo = r.get("cargo", "Não informado")
            local = r.get("local", "Não informado")
            geo_badge = r.get("geo_badge", "")
            if not geo_badge and isinstance(r.get("geo_info"), dict):
                geo_badge = r["geo_info"].get("badge", "")
            local_str = f"{local} {geo_badge}".strip() if geo_badge else local

            valor = r.get("valor", "Não informado")
            url = r.get("url", "")
            
            report += f"   <b>Cargo:</b> {escape_html(cargo)}\n"
            report += f"   <b>Local:</b> {escape_html(local_str)} | <b>Valor:</b> {escape_html(valor)} | <b>Prazo:</b> {escape_html(prazo)}{urg_tag}\n"
            if r.get("reasoning"):
                report += f"   <b>Aderência:</b> {escape_html(r['reasoning'])}\n"
            if url:
                report += f"   <b>Link:</b> <a href=\"{escape_html(url)}\">Acessar Oportunidade</a>\n\n"
            else:
                report += "\n"

    if all_medium:
        report += "<b>DESTAQUES DE MÉDIA ADERÊNCIA</b>\n\n"
        for idx, r in enumerate(all_medium, 1):
            prazo = r.get("prazo", "Não informado")
            urg_tag = " <code>[URGENTE]</code>" if check_urgency(prazo) else ""
            report += f"- <b>{escape_html(r['title'])}</b>{urg_tag} ({escape_html(r.get('local', 'Local N/A'))})\n"
            if r.get("url"):
                report += f"  <a href=\"{escape_html(r['url'])}\">Acessar Link</a>\n"

    if not all_high and not all_medium:
        report += "<i>Nenhuma oportunidade de alta ou média relevância encontrada em nenhuma das bases hoje.</i>\n"

    return report


def generate_briefing_pdf(briefing_text, pdf_path):
    """
    Gera versão executiva em PDF do briefing utilizando PyMuPDF.
    """
    try:
        import pymupdf as fitz
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # A4
        
        # Limpa tags HTML para o texto plano do PDF
        clean_text = re.sub(r"<[^>]+>", "", briefing_text)
        
        # Insere cabeçalho e corpo com tipografia limpa
        rect = fitz.Rect(50, 50, 545, 792)
        page.insert_textbox(rect, clean_text, fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
        
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        doc.save(pdf_path)
        doc.close()
        print(f"PDF executivo do briefing salvo em: {pdf_path}")
        return True
    except Exception as e:
        print(f"Aviso: Não foi possível gerar PDF do briefing ({e}).")
        return False


def send_initial_notification(grupo, total_editais):
    """Notificação de início sob demanda (opcional/silenciável)."""
    message = f"<b>I.C.A.R.O. ({grupo.upper()}):</b> Iniciando processamento semântico de {total_editais} novos editais."
    return send_telegram_message(message)
