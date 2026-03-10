# MKZ — Plateforme Éleveurs Lapins ↔ Acheteurs (Django + MySQL/XAMPP)

## Fonctionnalités incluses
- Comptes Éleveur / Acheteur
- Badge **Éleveur vérifié** (admin)
- Annonces (lapin vivant / viande) + **photos multiples**
- Recherche & filtres + bouton WhatsApp
- **Avis / notes** sur annonces
- **Tableau de bord éleveur** (mes annonces)
- API JSON (listings, details, reviews, profil)
- Paiement **MoMo/Orange (Phase 2)** : base technique + endpoints de démo (non branchés aux APIs réelles)

## Installation (Windows + XAMPP)
1) Démarre MySQL dans XAMPP
2) Dans phpMyAdmin, crée la DB : `rabbit_market`
3) Copie `.env.example` en `.env` et adapte si besoin

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Site: http://127.0.0.1:8000/
- Dashboard: http://127.0.0.1:8000/dashboard/
- Admin: http://127.0.0.1:8000/admin/

## Si mysqlclient ne s'installe pas (Windows)
Alternative : PyMySQL

```bash
pip install pymysql
```

Puis dans `MKZ/__init__.py`, mets:

```python
import pymysql
pymysql.install_as_MySQLdb()
```

## Paiements (Phase 2)
Dans `marketplace/payments.py`, tu as une structure propre :
- `initiate_payment()` crée une transaction
- `webhook_simulator()` simule un retour SUCCESS/FAILED

Pour brancher MTN MoMo / Orange Money, il faudra ajouter les appels HTTP vers leurs APIs (keys + callbacks).
