import os
import json
from playwright.sync_api import sync_playwright
import time

def get_new_opportunities(download_dir, processed_ids):
    os.makedirs(download_dir, exist_ok=True)
    opportunities = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        urls = [
            "https://www.ipea.gov.br/portal/bolsas-de-pesquisa",
            "https://www.ipea.gov.br/portal/consultorias"
        ]
        
        for base_url in urls:
            try:
                page.goto(base_url, timeout=30000, wait_until="domcontentloaded")
                # Wait for the table or list to load
                page.wait_for_timeout(2000)
                
                # IPEA results are usually inside .blog div or multiple items
                items = page.locator("div.item, div.row.item, div.list-item, h3").all()
                if not items:
                    # Let's search by links that contain "Chamada" or "Edital"
                    links = page.locator("a").all()
                    for link in links:
                        text = link.inner_text().strip()
                        href = link.get_attribute("href")
                        
                        if href and ("chamada-publica" in href.lower() or "edital" in href.lower()):
                            # Checa status
                            if "FECHADA" in text or "RESULTADO" in text or "ENCERRADA" in text:
                                continue
                                
                            opp_id = href.split("/")[-1]
                            if not opp_id or opp_id in processed_ids:
                                continue
                                
                            print(f"Nova oportunidade IPEA encontrada: {text}")
                            
                            # Clica para pegar detalhes
                            detail_url = href if href.startswith("http") else f"https://www.ipea.gov.br{href}"
                            
                            # Salva um arquivo .txt
                            file_path = os.path.join(download_dir, f"{opp_id}.txt")
                            try:
                                page_detail = browser.new_page()
                                page_detail.goto(detail_url, timeout=30000)
                                content = page_detail.locator("body").inner_text()
                                with open(file_path, "w", encoding="utf-8") as f:
                                    f.write(content)
                                page_detail.close()
                                
                                opportunities.append({
                                    "id": opp_id,
                                    "title": f"[IPEA] {text[:100]}",
                                    "end_date": "Ver Edital",
                                    "file_paths": [file_path],
                                    "source": "IPEA",
                                    "url": detail_url
                                })
                            except Exception as e:
                                print(f"Erro ao acessar detalhes {detail_url}: {e}")
                                
                else:
                    # Se tiver estrutura de blocos
                    blocks = page.locator("p:has-text('Chamada Pública')").all()
                    for block in blocks:
                        parent = block.locator("..")
                        text = parent.inner_text()
                        if "ABERTA" in text or "aberta" in text.lower():
                            link_elem = block.locator("a").first
                            if link_elem:
                                href = link_elem.get_attribute("href")
                                opp_id = href.split("/")[-1]
                                if opp_id in processed_ids:
                                    continue
                                
                                detail_url = href if href.startswith("http") else f"https://www.ipea.gov.br{href}"
                                file_path = os.path.join(download_dir, f"{opp_id}.txt")
                                
                                try:
                                    page_detail = browser.new_page()
                                    page_detail.goto(detail_url, timeout=30000)
                                    content = page_detail.locator("body").inner_text()
                                    with open(file_path, "w", encoding="utf-8") as f:
                                        f.write(content)
                                    page_detail.close()
                                    
                                    opportunities.append({
                                        "id": opp_id,
                                        "title": f"[IPEA] {block.inner_text()}",
                                        "end_date": "Ver Edital",
                                        "file_paths": [file_path],
                                        "source": "IPEA",
                                        "url": detail_url
                                    })
                                except Exception as e:
                                    pass

            except Exception as e:
                print(f"Erro ao raspar IPEA {base_url}: {e}")

        browser.close()
        
    return opportunities
