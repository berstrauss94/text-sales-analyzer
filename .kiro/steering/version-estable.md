---
inclusion: auto
---

# VERSION ESTABLE DE REFERENCIA

## Identificadores del respaldo

| Tipo | Nombre | Descripción |
|------|--------|-------------|
| Git Tag | `STABLE-v3-2026-05-23` | Tag principal de la versión estable |
| Git Tag | `BACKUP-STABLE-001` | Tag de respaldo adicional |
| Git Branch | `backup/stable-v3-2026-05-23` | Rama de respaldo en GitHub |
| Commit Hash | `a84a024` | Hash del commit estable en master |

## Fecha del respaldo
23 de Mayo de 2026 — post-rollback de sesión problemática

## Funcionalidades confirmadas en esta versión
- ✅ Análisis de textos con ML (intención, sentimiento, conceptos)
- ✅ Guardado de textos por admin (BaronVonBerna) asignados a usuarios
- ✅ Carga de textos guardados en dropdown por usuario/mes
- ✅ Torta gráfica general (Panel de Seguimiento Admin)
- ✅ Torta gráfica unitaria por texto analizado
- ✅ Informe completo por texto
- ✅ Indicadores comerciales con detalle por categoría
- ✅ Resaltado de palabras en texto con autoscroll

## Cómo restaurar esta versión

### Opción 1 — Restaurar archivos específicos:
```bash
git checkout STABLE-v3-2026-05-23 -- web_app.py src/users/history_manager.py src/components/commercial_analyzer.py src/components/concept_extractor.py
python deploy.py
```

### Opción 2 — Ver el código de esa versión:
```bash
git show STABLE-v3-2026-05-23:web_app.py > web_app_stable.py
```

### Opción 3 — Desde la rama de respaldo:
```bash
git checkout backup/stable-v3-2026-05-23
```

## REGLA IMPORTANTE
Antes de hacer cambios grandes, crear un nuevo tag:
```bash
git tag -a "STABLE-vX-YYYY-MM-DD" -m "descripcion"
git push origin STABLE-vX-YYYY-MM-DD
```
