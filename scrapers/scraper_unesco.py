import os
import time
from playwright.sync_api import sync_playwright

def get_new_opportunities(download_dir, processed_ids):
    os.makedirs(download_dir, exist_ok=True)
    new_opportunities = []
    
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        
        print("Acessando portal da UNESCO...")
        page.goto("https://roster.brasilia.unesco.org/app/selection-process-list", wait_until="networkidle")
        
        # Wait for table to load
        page.wait_for_selector("table tbody tr", timeout=30000)
        time.sleep(2) # Give Vue time to fully render
        
        rows = page.locator("table tbody tr").all()
        print(f"Encontradas {len(rows)} linhas na tabela da UNESCO.")
        
        for i, row in enumerate(rows):
            try:
                cols = row.locator("td").all()
                if len(cols) < 5:
                    continue
                    
                opp_id = "UNESCO_" + cols[0].inner_text().strip()
                title = cols[2].inner_text().strip()
                end_date = cols[4].inner_text().strip()
                
                if opp_id in processed_ids:
                    continue
                    
                print(f"Novo edital UNESCO detectado: {title}")
                
                # Click the View button
                view_btn = row.locator("button[data-original-title='View']")
                view_btn.click()
                
                # Wait for modal to load
                page.wait_for_selector("#modalViewSelectionProcess", state="visible")
                time.sleep(1) # wait for inner content to settle
                
                # Get download buttons
                download_btns = page.locator("#modalViewSelectionProcess button[data-original-title='Download']").all()
                pdf_files = []
                
                for btn_idx, btn in enumerate(download_btns):
                    with page.expect_download(timeout=30000) as download_info:
                        btn.click()
                    download = download_info.value
                    file_name = f"{opp_id}_file_{btn_idx}.pdf"
                    file_path = os.path.join(download_dir, file_name)
                    download.save_as(file_path)
                    pdf_files.append(file_path)
                
                # Close modal
                close_btn = page.locator("#modalViewSelectionProcess button.btn-close")
                close_btn.click()
                page.wait_for_selector("#modalViewSelectionProcess", state="hidden")
                
                if pdf_files:
                    new_opportunities.append({
                        "id": opp_id,
                        "title": f"[UNESCO] {title}",
                        "end_date": end_date,
                        "file_paths": pdf_files,
                        "source": "UNESCO",
                        "url": "https://pt.unesco.org/vagas"
                    })
            except Exception as e:
                print(f"Erro ao processar linha da UNESCO: {e}")
                # Try to close modal if it's stuck open
                try:
                    page.locator("#modalViewSelectionProcess button.btn-close").click(timeout=1000)
                except:
                    pass
                    
        browser.close()
        
    return new_opportunities

if __name__ == "__main__":
    opps = get_new_opportunities("pdfs_unesco", set())
    print(f"Total baixado: {len(opps)}")
