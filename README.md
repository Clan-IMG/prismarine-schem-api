# Prismarine Schem API

Konvertiert `.litematic`-Dateien (Litematica) im Arbeitsspeicher in das WorldEdit/FAWE-kompatible Sponge-Schematic-Format v2 (`.schem`).

## Endpoint

```
POST /api/v1/convert
```

- **Auth:** `Authorization: Bearer <API_TOKEN>` (erforderlich, außer für `/health`)
- **Request:** `multipart/form-data` mit Feld `file` (die `.litematic`-Datei)
- **Response:** `application/octet-stream` mit der fertigen `.schem`-Datei als Download

## Upload per curl

```bash
curl -X POST "https://<host>/api/v1/convert" \
  -H "Authorization: Bearer $API_TOKEN" \
  -F "file=@mein_bauwerk.litematic" \
  -o mein_bauwerk.schem
```

## Upload per Python (requests)

```python
import requests

url = "https://<host>/api/v1/convert"
headers = {"Authorization": "Bearer <API_TOKEN>"}

with open("mein_bauwerk.litematic", "rb") as f:
    response = requests.post(url, headers=headers, files={"file": f})

response.raise_for_status()
with open("mein_bauwerk.schem", "wb") as out:
    out.write(response.content)
```

## Fehler

| Status | Ursache |
|--------|---------|
| 400 | Datei fehlt, ist leer oder hat nicht die Endung `.litematic` |
| 401 | Fehlender oder ungültiger Bearer-Token |
| 500 | Fehler beim Parsen/Konvertieren der Litematic-Datei (Detail im JSON-Body) |
