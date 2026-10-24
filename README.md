# Chez Soi Rangé

Site d'idées de rangement pour petits espaces, et flux RSS lus automatiquement par Pinterest (@chezsoirange).

- `data/pins.json` : les épingles (titre, description, astuces, tableau, date de sortie `publish_at`).
- `tools/render.py` : génère les visuels 1000×1500.
- `tools/build.py` : construit le site dans `_site/` ; seules les épingles dont la date est passée sont publiées.
- `.github/workflows/publish.yml` : reconstruit et publie le site 3 fois par jour (GitHub Pages).
- Flux Pinterest : `/feeds/<tableau>.xml`, un flux par tableau.

Géré par Claude pour Julia. Ne pas supprimer d'épingle déjà publiée : Pinterest garde l'épingle, mais le lien deviendrait cassé.
