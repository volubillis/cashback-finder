# Ancien comparateur statique

Ce dépôt alimente GitHub Pages et la copie HTML Acer sur le port 8080. Il est distinct du nouveau comparateur `/cashback2/` et de sa collecte automatique Widilo.

Les données publiées sont dans `SEED` avec leurs dates d’observation. Le code de l’interface est maintenu dans `catalogue.js`, puis intégré dans `index.html` : l’HTML reste autonome pour le script existant `cashback-sync` sur Acer.

## Intégrer les CSV fournis

```text
python scripts/import_verified_snapshots.py --date AAAA-MM-JJ --rp chemin-rp.csv --rr chemin-rr.csv --tc chemin-tc.csv --wi chemin-wi.csv
python scripts/embed_catalogue.py
python scripts/embed_catalogue.py --check
node --check catalogue.js
node tests/catalogue.test.cjs
```

Chaque plateforme peut être fournie séparément. Les autres plateformes conservent leurs dates. Les fichiers de rapport et les observations normalisées sont enregistrés dans `updates/verified-AAAA-MM-JJ.json` et `data/releves-AAAA-MM-JJ.json`. Ils ne conservent pas les liens temporaires de redirection Réductions Privées.

Les doublons contradictoires, identifiants ambigus, taux mal formés et collectes anormalement courtes bloquent l’import. Plusieurs identifiants d’un marchand fusionné sont conservés. Une absence dans un relevé signale une observation ancienne conservée ; elle ne supprime pas le marchand. Un taux Widilo vide ne confirme pas un taux et n’efface pas sa dernière valeur connue : cette dernière reste datée séparément.

Le catalogue publié est prioritaire sur les anciens états de navigateur. Les imports locaux dont la date source est strictement plus récente restent utilisables ; à date égale le relevé publié fait référence. Catégories et liens personnels sont dans des clés de stockage séparées, conservées par la migration. Les imports sur la page restent locaux au navigateur, sans publication générale.

Ne plus lancer le script de synchronisation historique limité au 2 novembre pour mettre à jour ce catalogue. La mise à jour automatique des taux TopCashback demeure suspendue dans son ancien workflow ; l’intégration de CSV est une opération distincte.

## Publication

Publier les fichiers suivis dans le dépôt déclenche le workflow Pages. Vérifier sa réussite puis le fichier HTML effectivement servi, son empreinte et les fiches rendues dans le navigateur. Sur Acer, `sudo /usr/local/sbin/cashback-sync` copie l’HTML public GitHub vers `/var/www/cashback/index.html`, avec sauvegarde et remplacement atomique. Lancer cette commande seulement après vérification de la version publique. Aucun redémarrage de Caddy ni du nouveau comparateur n’est nécessaire.
