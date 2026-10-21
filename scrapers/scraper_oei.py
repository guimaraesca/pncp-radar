import os
import time
from playwright.sync_api import sync_playwright
import requests

def get_new_opportunities(download_dir, processed_ids):
    os.makedirs(download_dir, exist_ok=True)
    new_opportunities = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Acessando portal da OEI...")
        page.goto("https://oei.int/pt/licitacoes-y-convocatorias/", wait_until="networkidle")
        time.sleep(2)
        
        # OEI has a tags with class contracting__lite
        links = page.locator("a.contracting__lite").all()
        print(f"Encontradas {len(links)} oportunidades na OEI.")
        
        opps_to_process = []
        for link in links:
            opp_id = "OEI_" + link.get_attribute("data-id")
            title = link.get_attribute("data-title")
            href = link.get_attribute("href")
            
            if opp_id not in processed_ids:
                opps_to_process.append({"id": opp_id, "title": title, "href": href})
                
        # Now visit each href to find PDF
        for opp in opps_to_process:
            print(f"Novo edital OEI detectado: {opp['title']}")
            try:
                page.goto(opp['href'], wait_until="networkidle")
                time.sleep(1)
                
                # Find all links ending in .pdf
                pdf_links = page.locator("a[href$='.pdf']").all()
                pdf_files = []
                
                for idx, pdf_link in enumerate(pdf_links):
                    pdf_url = pdf_link.get_attribute("href")
                    if not pdf_url.startswith("http"):
                        pdf_url = "https://oei.int" + pdf_url
                        
                    file_name = f"{opp['id']}_file_{idx}.pdf"
                    file_path = os.path.join(download_dir, file_name)
                    
                    # Download PDF directly with requests since it's just a link
                    r = requests.get(pdf_url)
                    with open(file_path, 'wb') as f:
                        f.write(r.content)
                    pdf_files.append(file_path)
                
                if pdf_files:
                    href = opp.get("href", "")
                    oei_url = href if href.startswith("http") else f"https://oei.int{href if href.startswith('/') else '/' + href}"
                    new_opportunities.append({
                        "id": opp['id'],
                        "title": f"[OEI] {opp['title']}",
                        "end_date": "Não informada",
                        "file_paths": pdf_files,
                        "source": "OEI",
                        "url": oei_url
                    })
            except Exception as e:
                print(f"Erro ao processar OEI {opp['title']}: {e}")
                
        browser.close()
        
    return new_opportunities

if __name__ == "__main__":
    opps = get_new_opportunities("pdfs_oei", set())
    print(f"Total baixado: {len(opps)}")
