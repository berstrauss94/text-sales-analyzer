# -*- coding: utf-8 -*-
"""
Test rápido del scraper reescrito.
"""
import os
os.environ["MPC_USERNAME"] = "ber.strss@gmail.com"
os.environ["MPC_PASSWORD"] = "1234"

from src.components.mpc_scraper import MPCScraper

scraper = MPCScraper()
scraper.login()
print(f"Periodos disponibles: {list(scraper._periodo_map.items())[:8]}")

# Probar con Enero 2026 — solo los primeros 3 registros con transcripción
print("\nFetching Enero 2026...")
records = scraper.fetch_records(month=1, year=2026)
print(f"Total registros: {len(records)}")
transcriptos = [r for r in records if r.get("transcripcion")]
print(f"Con transcripción: {len(transcriptos)}")

if transcriptos:
    r = transcriptos[0]
    print(f"\nPrimer registro con transcripción:")
    print(f"  id:        {r['id']}")
    print(f"  vendedor:  {r['vendedor']}")
    print(f"  fecha:     {r['fecha_grabacion']}")
    print(f"  estado:    {r['estado']}")
    print(f"  transcripcion ({len(r['transcripcion'])} chars):")
    print(f"  {r['transcripcion'][:300]}")
