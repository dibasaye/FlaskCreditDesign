# FinanceManager - Système de Gestion de Crédit & Épargne

## Vue d'ensemble
Application web Flask complète pour la gestion des produits de crédit et d'épargne destinée aux institutions financières (banques, coopératives, microfinance).

## Fonctionnalités principales

### Gestion des Clients
- Création et modification des profils clients avec identifiants uniques
- Informations complètes (nom, email, téléphone, adresse, date de naissance, numéro d'identité)
- Historique complet des crédits et comptes d'épargne
- Vue détaillée de chaque client

### Gestion des Produits
- Création de produits de crédit et d'épargne
- Paramétrage des taux d'intérêt, montants min/max, durées
- Activation/désactivation des produits
- Description et conditions personnalisables

### Gestion des Crédits
- Soumission de demandes de crédit
- Workflow d'approbation (Pending → Approved → Active → Completed)
- Calcul automatique des intérêts et échéances mensuelles
- Suivi des remboursements avec barre de progression
- Historique complet des paiements
- Contrôle d'accès par rôle pour approbation/décaissement

### Gestion de l'Épargne
- Ouverture de comptes d'épargne
- Dépôts et retraits avec validation de solde
- Calcul automatique et affichage du solde après transaction
- Historique détaillé des transactions
- Paramétrage des taux d'intérêt par produit

### Tableau de Bord
- Statistiques en temps réel (clients, crédits actifs, épargne totale, demandes en attente)
- Graphiques interactifs (Chart.js) pour visualisation des données
- Montants totaux décaissés, remboursés et restants
- Liste des crédits et clients récents

### Authentification & Sécurité
- Système de connexion sécurisé avec Flask-Login
- Gestion des rôles (administrateur, gestionnaire, agent)
- Mots de passe hashés avec Werkzeug
- Compte administrateur configuré via variables d'environnement sécurisées
- Protection des routes selon les rôles
- Pas de mots de passe en dur dans le code

## Architecture Technique

### Backend
- **Framework**: Flask 3.1.2
- **ORM**: SQLAlchemy avec Flask-SQLAlchemy
- **Base de données**: PostgreSQL (Neon)
- **Authentification**: Flask-Login
- **Formulaires**: Flask-WTF avec validation
- **Sécurité**: Werkzeug pour hashage de mots de passe

### Frontend
- **Framework CSS**: Bootstrap 5.3.0
- **Icônes**: Font Awesome 6.4.0
- **Graphiques**: Chart.js 4.4.0
- **Design**: CSS personnalisé avec palette de couleurs professionnelle
- **Animations**: Transitions CSS fluides et modernes
- **Responsive**: Interface adaptée mobile et desktop

### Modèles de Données
1. **User**: Utilisateurs avec rôles
2. **Client**: Clients de l'institution
3. **Product**: Produits de crédit et d'épargne
4. **Credit**: Demandes et suivi de crédits
5. **CreditPayment**: Paiements de remboursement
6. **SavingsAccount**: Comptes d'épargne
7. **SavingsTransaction**: Transactions d'épargne

## Structure du Projet
```
.
├── main.py                 # Application Flask principale
├── models.py               # Modèles SQLAlchemy
├── forms.py                # Formulaires WTForms
├── templates/              # Templates Jinja2
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── clients.html
│   ├── client_form.html
│   ├── client_detail.html
│   ├── products.html
│   ├── product_form.html
│   ├── credits.html
│   ├── credit_form.html
│   ├── credit_detail.html
│   ├── savings.html
│   ├── savings_form.html
│   └── savings_detail.html
└── static/
    └── css/
        └── style.css       # Styles personnalisés
```

## Design & Interface
- **Palette de couleurs**: Bleu professionnel (#2563eb), vert (#059669), violet (#8b5cf6)
- **Style**: Moderne, épuré avec dégradés subtils
- **Cartes**: Ombres douces, coins arrondis, animations au survol
- **Navigation**: Barre de navigation fixe avec menu déroulant utilisateur
- **Formulaires**: Champs bien espacés, validation visuelle
- **Tableaux**: Hover effects, tri visuel

## Configuration Requise

### Variables d'Environnement
- `DATABASE_URL`: URL de connexion PostgreSQL
- `SESSION_SECRET`: Clé secrète pour les sessions Flask
- `ADMIN_USERNAME`: Nom d'utilisateur administrateur initial
- `ADMIN_PASSWORD`: Mot de passe administrateur initial
- `ADMIN_EMAIL`: Email de l'administrateur

### Dépendances Python
- flask
- flask-login
- flask-wtf
- flask-sqlalchemy
- psycopg2-binary
- python-dateutil
- email-validator

## Déploiement
Le serveur démarre sur `0.0.0.0:5000` en mode debug pour le développement.

## Fonctionnalités Récentes (Octobre 2025)
- ✅ **Simulation de prêts** : Calculateur interactif sans création de crédit
- ✅ **Échéancier de paiement** : Génération automatique lors du décaissement
- ✅ **Calcul des pénalités** : Pénalités automatiques pour retards de paiement
- ✅ **Intérêts d'épargne** : Calcul et application automatique des intérêts
- ✅ **Clôture de comptes** : Fermeture sécurisée des comptes d'épargne
- ✅ **Audit trail** : Traçabilité complète des activités importantes
- ✅ **Historique des interactions** : Suivi des communications avec les clients
- ✅ **Analyse de solvabilité** : Score de crédit automatique pour chaque client
- ✅ **Rapports avancés** : Tableaux de bord avec analyses de performance et risques
- ✅ **Gestion des garanties** : Enregistrement des garanties pour les crédits

### Nouvelles Fonctionnalités Avancées (23 Octobre 2025)
- ✅ **Page Paramètres Complète** : Interface à onglets pour configuration système
  - Profil utilisateur et changement de mot de passe
  - Paramètres système (devise, langue, format date, taux de pénalité)
  - Gestion des notifications et sauvegardes automatiques
  - Méthodes de calcul des intérêts configurables
  
- ✅ **Gestion des Utilisateurs** : Administration complète des comptes
  - Création, modification et suppression d'utilisateurs
  - Gestion des rôles (Administrateur, Gestionnaire, Agent)
  - Interface intuitive avec contrôles de sécurité
  
- ✅ **Système de Notifications** : Centre de notifications intégré
  - Badge de notifications non lues dans la navigation
  - Page dédiée avec pagination
  - Marquage individuel ou global des notifications
  - Types de notifications (crédits, paiements, alertes, système)
  
- ✅ **Export de Données** : Extraction CSV pour analyse
  - Export complet des clients avec toutes informations
  - Export des crédits avec détails et statuts
  - Export des comptes d'épargne et soldes
  - Fichiers CSV formatés et prêts pour Excel
  
- ✅ **Design Moderne et Responsive** : Interface professionnelle
  - Animations fluides et transitions élégantes
  - Onglets Bootstrap avec effets visuels
  - Badge de notifications animé
  - Fil d'Ariane (breadcrumbs) pour navigation
  - Interface adaptative mobile et desktop

### 🏆 FONCTIONNALITÉS NIVEAU 1 - COMPÉTITION (23 Octobre 2025)

#### 📊 Dashboard Analytics Avancés
- **Graphiques interactifs Chart.js** : Visualisation professionnelle des données
  - Courbe des tendances de crédits sur 6 mois (Line chart)
  - Répartition par statut des crédits (Donut chart)
  - Comparaison mensuelle des décaissements (Bar chart)
- **KPIs enrichis** : Statistiques en temps réel avec tendances
  - Taux d'approbation, taux de remboursement, portfolio à risque
  - Montants totaux : décaissés, remboursés, en attente
- **Performance metrics** : Suivi des indicateurs clés de performance

#### 📈 Page Analytics Dédiée
- **Prédictions et projections** : Analyse prédictive des revenus futurs
- **Top 10 Clients VIP** : Identification des clients les plus rentables
- **Analyse de qualité du portefeuille** : PAR (Portfolio at Risk) détaillé
  - PAR30, PAR60, PAR90 avec indicateurs de santé
- **Statistiques de performance** : Analyse mensuelle complète
- **Gestion des risques** : Identification des clients à risque élevé

#### 🗺️ Carte Interactive Géographique
- **Leaflet.js + OpenStreetMap** : Carte interactive gratuite et performante
- **Visualisation des clients** : Marqueurs colorés par statut
  - Vert : Clients actifs avec bon historique
  - Orange : Clients à risque modéré
  - Rouge : Clients à risque élevé
- **Clustering intelligent** : Regroupement automatique pour grandes données
- **Popups informatifs** : Détails complets au clic
  - Nom, téléphone, email, adresse
  - Nombre de crédits actifs et statut
  - Liens directs vers profil client
- **Contrôles de zoom** : Navigation fluide et intuitive

#### 📱 Progressive Web App (PWA)
- **Installable sur mobile** : Fonctionne comme une app native
- **manifest.json complet** : Configuration PWA professionnelle
  - Icônes SVG 192px et 512px avec dégradés
  - Raccourcis rapides vers fonctionnalités clés
  - Thème et couleurs personnalisées
- **Service Worker** : Fonctionnement hors ligne
  - Cache des ressources statiques (CSS, JS)
  - Stratégie Network-first pour contenus dynamiques
  - Cache-first pour assets statiques
- **Expérience offline** : Application utilisable sans connexion
- **Add to Home Screen** : Installation en un clic

#### 📲 Design Mobile & Tablette Optimisé
- **Media queries complètes** : Responsive design professionnel
  - Breakpoints : 992px (tablette), 768px (mobile), 576px (petit mobile)
  - Adaptation automatique des layouts et typographie
- **Touch-friendly** : Cibles tactiles de 44px minimum (standard Apple)
- **Performance mobile** : 
  - Graphiques optimisés pour petits écrans
  - Tables scrollables et compactes
  - Formulaires sans zoom iOS
- **Modals plein écran** : Meilleure UX sur petits écrans
- **Dark mode support** : Thème sombre pour mode nuit PWA
- **Print styles** : Impression propre des rapports

## Améliorations Futures
- Génération de rapports PDF exportables avec graphiques
- Système d'alertes automatiques par email/SMS
- Recherche et filtrage avancés dans toutes les sections
- API REST pour intégrations tierces
- Gestion des documents et pièces jointes
