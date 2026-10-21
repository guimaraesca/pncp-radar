import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from core.filter_utils import is_relevant_opportunity, is_past_year

def get_new_opportunities(download_dir, processed_ids):
    os.makedirs(download_dir, exist_ok=True)
    base_url = 'https://www.dn.senac.br/quem-somos/trabalhe-conosco/'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        res = requests.get(base_url, headers=headers, timeout=30)
        res.raise_for_status()
    except Exception as e:
        print(f"Erro ao acessar Senac: {e}")
        return []

    soup = BeautifulSoup(res.text, 'html.parser')
    links = soup.find_all('a', href=True)
    
    opportunities = []
    
    for link in links:
        href = link.get('href')
        text = link.text.strip()
        
        # Filtra os links que parecem ser de vagas/editais
        if not text:
            continue
            
        lower_href = href.lower()
        if 'processo' in lower_href or 'edital' in lower_href or re.search(r'\d{1,3}-\d{4}', lower_href):
            # Ignora links de menu genéricos
            if href == base_url or href.endswith('/processo-seletivo/'):
                continue
                
            opp_id = href.strip('/').split('/')[-1]
            if not opp_id or len(opp_id) < 5:
                continue
                
            if opp_id in processed_ids:
                continue
                
            # Descarta processos de anos anteriores (ex: 2024, 2025)
            if is_past_year(text) or is_past_year(href):
                processed_ids.add(opp_id)
                continue
                
            # Pré-filtro rigoroso: ignora etapas intermediárias e cargos fora de escopo
            if not is_relevant_opportunity(text):
                # Marca como processado para não avaliar de novo
                processed_ids.add(opp_id)
                continue
                
            print(f"[Senac] Vaga relevante encontrada: {text}")
            
            full_href = urljoin(base_url, href)
            
            # Entra na página da vaga para pegar os PDFs
            try:
                opp_res = requests.get(full_href, headers=headers, timeout=30)
                opp_soup = BeautifulSoup(opp_res.text, 'html.parser')
                pdf_links = opp_soup.find_all('a', href=True)
                
                pdf_paths = []
                for pl in pdf_links:
                    phref = pl.get('href')
                    if phref.lower().endswith('.pdf'):
                        if any(k in phref.lower() for k in ['tutorial', 'gabarito', 'resultado', 'agenda']):
                            continue # Ignora tutoriais e resultados
                            
                        pdf_url = urljoin(full_href, phref)
                        pdf_name = f"senac_{opp_id}_{phref.split('/')[-1]}"
                        pdf_path = os.path.join(download_dir, pdf_name)
                        
                        try:
                            pdf_data = requests.get(pdf_url, headers=headers, timeout=30).content
                            with open(pdf_path, 'wb') as f:
                                f.write(pdf_data)
                            pdf_paths.append(pdf_path)
                        except Exception as e:
                            print(f"[Senac] Erro ao baixar PDF {pdf_url}: {e}")
                
                if pdf_paths:
                    opportunities.append({
                        "id": opp_id,
                        "title": f"[Senac] {text}",
                        "end_date": "N/A",
                        "file_paths": pdf_paths,
                        "source": "Senac",
                        "url": full_href
                    })
            except Exception as e:
                print(f"[Senac] Erro ao acessar vaga {full_href}: {e}")

    return opportunities
