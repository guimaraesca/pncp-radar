import os
import time
from playwright.sync_api import sync_playwright

def get_new_opportunities(download_dir, processed_ids):
    """
    Scrapes the PNUD opportunities page, downloads new ZIP files.
    Returns a list of dicts: {'id': '146270', 'title': '...', 'file_path': '...', 'end_date': '...'}
    """
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    new_opportunities = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://parceiros.undp.org.br/opportunities", wait_until="networkidle")
        
        try:
            page.wait_for_selector("mat-row", timeout=10000)
            rows = page.locator("mat-row").all()
        except Exception as e:
            print(f"Error waiting for table rows: {e}")
            browser.close()
            return new_opportunities

        for row in rows:
            title = row.locator(".mat-column-title").inner_text().strip()
            end_date = row.locator(".mat-column-endDate").inner_text().strip()
            
            # Start download to get the filename (which contains the ID)
            try:
                with page.expect_download(timeout=30000) as download_info:
                    row.locator("button").click()
                
                download = download_info.value
                file_name = download.suggested_filename
                opp_id = file_name.replace(".zip", "")
                
                if opp_id in processed_ids:
                    # Already processed, skip downloading to disk
                    download.cancel()
                    continue
                    
                # It's a new opportunity
                file_path = os.path.join(download_dir, file_name)
                download.save_as(file_path)
                
                new_opportunities.append({
                    "id": opp_id,
                    "title": title,
                    "end_date": end_date,
                    "file_path": file_path,
                    "url": "https://parceiros.undp.org.br/opportunities"
                })
            except Exception as e:
                print(f"Skipping row due to error or no download: {e}")
            
            time.sleep(1) # Be nice to the server

        browser.close()
    
    return new_opportunities

if __name__ == "__main__":
    # Test run
    print(get_new_opportunities("editais_baixados", []))
