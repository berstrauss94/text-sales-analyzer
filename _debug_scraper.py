# -*- coding: utf-8 -*-
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
print("Login done. Cookies:", dict(session.cookies))

# Access grabaciones page
resp = session.get("https://www.miprimercasa.ar/Administracion/GRABACIONAUDITORSUBE.aspx", timeout=30)
print("Status:", resp.status_code, "URL:", resp.url)
soup = BeautifulSoup(resp.text, "html.parser")

# Find all select/dropdowns
selects = soup.find_all("select")
print(f"\nFound {len(selects)} dropdowns:")
for s in selects:
    name = s.get("name", "")
    sid = s.get("id", "")
    opts = s.find_all("option")
    opt_texts = [o.get_text(strip=True) for o in opts[:8]]
    opt_vals  = [o.get("value","") for o in opts[:8]]
    print(f"  name={name!r} id={sid!r}")
    print(f"  options: {list(zip(opt_vals, opt_texts))}")

# Find submit buttons
print("\nSubmit buttons:")
for btn in soup.find_all("input", {"type": "submit"}):
    print(f"  name={btn.get('name')!r} value={btn.get('value')!r}")

# Find table
print("\nTable:")
table = soup.find("table")
if table:
    rows = table.find_all("tr")
    print(f"  {len(rows)} rows")
    if rows:
        print("  Header:", [td.get_text(strip=True) for td in rows[0].find_all(["th","td"])])
        for row in rows[1:4]:
            print("  Row:", [td.get_text(strip=True)[:40] for td in row.find_all("td")])
else:
    print("  No table found")
    # Print a chunk of the page to understand structure
    print(resp.text[1000:3000])
