import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def get_new_opportunities(download_dir, processed_ids):
    os.makedirs(download_dir, exist_ok=True)
    base_url = 'https://brazil.unfpa.org/pt-br/vacancies'
    host_url = 'https://brazil.unfpa.org'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        res = requests.get(base_url, headers=headers, timeout=30)
        res.raise_for_status()
    except Exception as e:
        print(f"Erro ao acessar UNFPA: {e}")
        return []

    soup = BeautifulSoup(res.text, 'html.parser')
    links = soup.find_all('a', href=True)
    
    opportunities = []
    
    for link in links:
        href = link.get('href')
        text = link.text.strip()
        
        lower_href = href.lower()
        if 'vacancy' in lower_href or 'vaga' in lower_href or 'consultor' in text.lower() or 'assistente' in text.lower():
            if href == '/pt-br/vacancies' or href == base_url or len(text) < 5:
                continue
            
            # id
            opp_id = href.strip('/').split('/')[-1]
            if not opp_id or opp_id in processed_ids:
                continue
                
            full_url = urljoin(host_url, href)
            print(f"[UNFPA] Nova vaga encontrada: {text}")
            
            try:
                opp_res = requests.get(full_url, headers=headers, timeout=30)
                opp_soup = BeautifulSoup(opp_res.text, 'html.parser')
                pdf_links = opp_soup.find_all('a', href=True)
                
                pdf_paths = []
                for pl in pdf_links:
                    phref = pl.get('href')
                    if phref.lower().endswith('.pdf'):
                        pdf_url = urljoin(full_url, phref)
                        pdf_name = f"unfpa_{opp_id}_{phref.split('/')[-1]}"
                        pdf_path = os.path.join(download_dir, pdf_name)
                        
                        try:
                            pdf_data = requests.get(pdf_url, headers=headers, timeout=30).content
                            with open(pdf_path, 'wb') as f:
                                f.write(pdf_data)
                            pdf_paths.append(pdf_path)
                        except Exception as e:
                            print(f"[UNFPA] Erro ao baixar PDF {pdf_url}: {e}")
                
                if pdf_paths:
                    opportunities.append({
                        "id": opp_id,
                        "title": f"[UNFPA] {text}",
                        "end_date": "N/A",
                        "file_paths": pdf_paths,
                        "source": "UNFPA",
                        "url": href
                    })
            except Exception as e:
                print(f"[UNFPA] Erro ao acessar vaga {full_url}: {e}")

    return opportunities
