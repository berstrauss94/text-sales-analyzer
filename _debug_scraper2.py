# -*- coding: utf-8 -*-
"""
Debug: entender cómo filtrar por mes y obtener transcripciones.
"""
import requests
from bs4 import BeautifulSoup

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

# Login
resp = session.get("https://www.miprimercasa.ar/acceso.aspx", timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")
payload = {}
for inp in soup.find_all("input", {"type": "hidden"}):
    if inp.get("name"):
        payload[inp["name"]] = inp.get("value", "")
payload["otxtUsuario"] = "ber.strss@gmail.com"
payload["otxtPass"] = "1234"
payload["obutAcceder"] = "Ingresar al Sistema"
session.post("https://www.miprimercasa.ar/acceso.aspx", data=payload, timeout=30)

# Access grabaciones page
resp = session.get("https://www.miprimercasa.ar/Administracion/GRABACIONAUDITORSUBE.aspx", timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")

# Get all hidden fields
hidden = {}
for inp in soup.find_all("input", {"type": "hidden"}):
    if inp.get("name"):
        hidden[inp["name"]] = inp.get("value", "")

print("Hidden fields:", list(hidden.keys()))

# Try filtering by Enero 2026 (id=85) via ASP.NET postback
post_payload = dict(hidden)
post_payload["ctl00$ContentPlaceHolder1$oddlUltimosPeriodos"] = "85"  # Enero 2026
post_payload["ctl00$ContentPlaceHolder1$oddlVendedor"] = "0"  # TODOS
# ASP.NET postback trigger
post_payload["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$oddlUltimosPeriodos"
post_payload["__EVENTARGUMENT"] = ""

resp2 = session.post(
    "https://www.miprimercasa.ar/Administracion/GRABACIONAUDITORSUBE.aspx",
    data=post_payload,
    timeout=30
)
soup2 = BeautifulSoup(resp2.text, "html.parser")
table = soup2.find("table")
if table:
    rows = table.find_all("tr")
    print(f"\nEnero 2026: {len(rows)-1} registros")
    print("Header:", [td.get_text(strip=True) for td in rows[0].find_all(["th","td"])])
    for row in rows[1:4]:
        cells = [td.get_text(strip=True)[:50] for td in row.find_all("td")]
        print("  Row:", cells)
        # Check for links
        links = row.find_all("a")
        for lnk in links:
            print("    Link:", lnk.get("href",""), lnk.get_text(strip=True)[:30])
else:
    print("No table in filtered response")
    print(resp2.text[500:2000])

# Now check what happens when clicking on a row - look for detail page
print("\n--- Checking detail page ---")
# Try with first record id from current page
resp3 = session.get("https://www.miprimercasa.ar/Administracion/GRABACIONAUDITORSUBE.aspx", timeout=30)
soup3 = BeautifulSoup(resp3.text, "html.parser")
table3 = soup3.find("table")
if table3:
    rows3 = table3.find_all("tr")
    if len(rows3) > 1:
        first_row = rows3[1]
        cells = first_row.find_all("td")
        record_id = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        print(f"First record id: {record_id}")
        # Check all links in row
        for lnk in first_row.find_all("a"):
            print(f"  Link href={lnk.get('href')!r} text={lnk.get_text(strip=True)!r}")
        # Try detail URL
        if record_id:
            detail_resp = session.get(
                f"https://www.miprimercasa.ar/Administracion/GRABACIONAUDITORSUBEDETALLE.aspx?id={record_id}",
                timeout=30
            )
            print(f"Detail status: {detail_resp.status_code} url: {detail_resp.url}")
            detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
            # Find textareas
            for ta in detail_soup.find_all("textarea"):
                print(f"  Textarea name={ta.get('name')!r} len={len(ta.get_text())}")
                print(f"  Content preview: {ta.get_text(strip=True)[:200]}")
            # Find any div with transcripcion
            for div in detail_soup.find_all(["div","p","span"], id=lambda x: x and "transcri" in x.lower()):
                print(f"  Transcripcion div: {div.get_text(strip=True)[:200]}")
            # Print a chunk of the detail page
            print("Detail page snippet:", detail_resp.text[1000:3000])
