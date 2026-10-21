import os
import time
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
import requests

def get_new_opportunities(download_dir, processed_ids):
    os.makedirs(download_dir, exist_ok=True)
    base_url = 'https://www.unicef.org/brazil/oportunidade-de-trabalho'
    host_url = 'https://www.unicef.org'
    
    opportunities = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        })
        
        try:
            page.goto(base_url, timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # Pega os links de vagas
            links = page.query_selector_all("a")
            for link in links:
                href = link.get_attribute("href")
                text = link.inner_text().strip()
                
                if not href or not text:
                    continue
                    
                if '/oportunidade-de-trabalho/' in href and href != '/brazil/oportunidade-de-trabalho':
                    opp_id = href.strip('/').split('/')[-1]
                    
                    if not opp_id or opp_id in processed_ids:
                        continue
                        
                    full_url = urljoin(host_url, href) if not href.startswith('http') else href
                    print(f"[UNICEF] Nova vaga encontrada: {text}")
                    
                    # Salva a própria página da vaga como .txt já que a UNICEF descreve a vaga na página
                    try:
                        # Entra na página da vaga para capturar o conteúdo
                        vaga_page = browser.new_page()
                        vaga_page.set_extra_http_headers({
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        })
                        vaga_page.goto(full_url, timeout=60000)
                        vaga_text = vaga_page.evaluate("document.body.innerText")
                        vaga_page.close()
                        
                        txt_name = f"unicef_{opp_id}.txt"
                        txt_path = os.path.join(download_dir, txt_name)
                        
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(f"URL: {full_url}\n\n{vaga_text}")
                            
                        opportunities.append({
                            "id": opp_id,
                            "title": f"[UNICEF] {text[:100]}",
                            "end_date": "N/A",
                            "file_paths": [txt_path],
                            "source": "UNICEF",
                            "url": full_url
                        })
                        
                    except Exception as e:
                        print(f"[UNICEF] Erro ao acessar a vaga {full_url}: {e}")
                        
        except Exception as e:
            print(f"Erro ao acessar UNICEF: {e}")
            
        finally:
            browser.close()

    return opportunities
