# -*- coding: utf-8 -*-
"""
Debug: entender cómo obtener la transcripción haciendo postback en una fila.
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

# Get hidden fields
hidden = {}
for inp in soup.find_all("input", {"type": "hidden"}):
    if inp.get("name"):
        hidden[inp["name"]] = inp.get("value", "")

# Filter Enero 2026
post_payload = dict(hidden)
post_payload["ctl00$ContentPlaceHolder1$oddlUltimosPeriodos"] = "85"
post_payload["ctl00$ContentPlaceHolder1$oddlVendedor"] = "0"
post_payload["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$oddlUltimosPeriodos"
post_payload["__EVENTARGUMENT"] = ""

resp2 = session.post(
    "https://www.miprimercasa.ar/Administracion/GRABACIONAUDITORSUBE.aspx",
    data=post_payload, timeout=30
)
soup2 = BeautifulSoup(resp2.text, "html.parser")

# Get updated hidden fields
hidden2 = {}
for inp in soup2.find_all("input", {"type": "hidden"}):
    if inp.get("name"):
        hidden2[inp["name"]] = inp.get("value", "")

# Find first row with "Grabacion transcripta"
table = soup2.find("table")
rows = table.find_all("tr") if table else []
print(f"Total rows: {len(rows)-1}")

# Find first transcripta row
target_row_idx = None
for i, row in enumerate(rows[1:], 0):
    cells = row.find_all("td")
    if len(cells) > 6:
        estado = cells[6].get_text(strip=True)
        if "transcripta" in estado.lower():
            target_row_idx = i
            record_id = cells[1].get_text(strip=True)
            vendedor = cells[4].get_text(strip=True)
            fecha = cells[5].get_text(strip=True)
            print(f"First transcripta row: idx={i} id={record_id} vendedor={vendedor} fecha={fecha}")
            break

if target_row_idx is not None:
    # Do postback Select$N
    select_payload = dict(hidden2)
    select_payload["ctl00$ContentPlaceHolder1$oddlUltimosPeriodos"] = "85"
    select_payload["ctl00$ContentPlaceHolder1$oddlVendedor"] = "0"
    select_payload["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$ogvGrabacionesRegistroTraer"
    select_payload["__EVENTARGUMENT"] = f"Select${target_row_idx}"

    resp3 = session.post(
        "https://www.miprimercasa.ar/Administracion/GRABACIONAUDITORSUBE.aspx",
        data=select_payload, timeout=30
    )
    soup3 = BeautifulSoup(resp3.text, "html.parser")
    print(f"\nPostback response status: {resp3.status_code}")

    # Look for textareas
    textareas = soup3.find_all("textarea")
    print(f"Textareas found: {len(textareas)}")
    for ta in textareas:
        content = ta.get_text(strip=True)
        print(f"  name={ta.get('name')!r} id={ta.get('id')!r} len={len(content)}")
        if content:
            print(f"  Preview: {content[:300]}")

    # Look for any element with transcripcion in id/name/class
    for el in soup3.find_all(True):
        eid = (el.get("id") or "").lower()
        ename = (el.get("name") or "").lower()
        eclass = " ".join(el.get("class") or []).lower()
        if any("transcri" in x for x in [eid, ename, eclass]):
            print(f"\nTranscripcion element: tag={el.name} id={el.get('id')} name={el.get('name')}")
            print(f"  Content: {el.get_text(strip=True)[:300]}")

    # Print a section of the page around any large text block
    # Find all divs/panels that might contain the transcription
    for div in soup3.find_all(["div", "panel", "section"]):
        text = div.get_text(strip=True)
        if len(text) > 200 and "grabaci" not in text[:50].lower():
            did = div.get("id","")
            dclass = " ".join(div.get("class") or [])
            if did or dclass:
                print(f"\nLarge div id={did!r} class={dclass!r}")
                print(f"  Text preview: {text[:400]}")
                break

    # Also dump all input fields visible (not hidden) to see what's on the page
    print("\nVisible inputs after select:")
    for inp in soup3.find_all("input"):
        if inp.get("type") != "hidden":
            print(f"  type={inp.get('type')!r} name={inp.get('name')!r} id={inp.get('id')!r} value={inp.get('value','')[:50]!r}")
