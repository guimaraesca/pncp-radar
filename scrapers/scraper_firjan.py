import os
import time
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from core.filter_utils import is_relevant_opportunity

def get_new_opportunities(download_dir, processed_ids):
    os.makedirs(download_dir, exist_ok=True)
    base_url = 'https://jobs.i-hunter.com/firjan/oportunidades'
    host_url = 'https://jobs.i-hunter.com'
    
    opportunities = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
        
        try:
            page.goto(base_url, timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            links = page.query_selector_all("a")
            for link in links:
                href = link.get_attribute("href")
                text = link.inner_text().strip()
                
                if not href or not text:
                    continue
                    
                if '/vaga/' in href.lower() or 'oportunidade' in href.lower():
                    if href == base_url or href == '/firjan/oportunidades':
                        continue
                        
                    opp_id = href.strip('/').split('/')[-1]
                    opp_id = ''.join(e for e in opp_id if e.isalnum())
                    
                    if not opp_id or len(opp_id) < 4 or opp_id in processed_ids:
                        continue
                        
                    # Pré-filtro de relevância no título antes de abrir aba do navegador
                    if not is_relevant_opportunity(text):
                        processed_ids.add(opp_id)
                        continue
                        
                    full_url = href if href.startswith('http') else urljoin(host_url, href)
                    print(f"[Firjan] Vaga relevante encontrada: {text}")
                    
                    try:
                        vaga_page = browser.new_page()
                        vaga_page.goto(full_url, timeout=30000)
                        vaga_page.wait_for_load_state("domcontentloaded", timeout=10000)
                        time.sleep(1)
                        
                        vaga_text = vaga_page.evaluate("document.body.innerText")
                        vaga_page.close()
                        
                        txt_name = f"firjan_{opp_id}.txt"
                        txt_path = os.path.join(download_dir, txt_name)
                        
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(f"URL: {full_url}\n\n{vaga_text}")
                            
                        opportunities.append({
                            "id": opp_id,
                            "title": f"[Firjan] {text[:100]}",
                            "end_date": "N/A",
                            "file_paths": [txt_path],
                            "source": "Firjan",
                            "url": full_url
                        })
                        
                    except Exception as e:
                        print(f"[Firjan] Erro ao acessar a vaga {full_url}: {e}")
                        
        except Exception as e:
            print(f"Erro ao acessar Firjan: {e}")
            
        finally:
            browser.close()

    return opportunities
