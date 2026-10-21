import os
from playwright.sync_api import sync_playwright

def get_new_opportunities(download_dir, processed_ids):
    os.makedirs(download_dir, exist_ok=True)
    opportunities = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            print("Buscando IICA...")
            page.goto("https://iica.int/pt/oportunidades", timeout=60000)
            page.wait_for_timeout(2000)
            
            # Buscando links que parecem ser vagas/consultorias
            links = page.locator("a").all()
            for link in links:
                text = link.inner_text().strip()
                href = link.get_attribute("href") or ""
                
                if "consultor" in text.lower() or "edital" in text.lower() or "termo" in text.lower():
                    opp_id = href.split("/")[-1] or text[:15].replace(" ", "_")
                    if opp_id in processed_ids or not href:
                        continue
                        
                    detail_url = href if href.startswith("http") else f"https://iica.int{href}"
                    print(f"Nova oportunidade IICA: {text}")
                    
                    file_path = os.path.join(download_dir, f"{opp_id}.txt")
                    try:
                        # Extrai info da pagina de detalhe
                        page_detail = browser.new_page()
                        page_detail.goto(detail_url, timeout=30000)
                        content = page_detail.locator("body").inner_text()
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        page_detail.close()
                        
                        opportunities.append({
                            "id": opp_id,
                            "title": f"[IICA] {text[:100]}",
                            "end_date": "Ver edital",
                            "file_paths": [file_path],
                            "source": "IICA",
                            "url": detail_url
                        })
                    except Exception as e:
                        print(f"Erro ao acessar detalhes IICA {detail_url}: {e}")
                        
        except Exception as e:
            print(f"Erro na requisição IICA: {e}")
            
        browser.close()
            
    return opportunities
