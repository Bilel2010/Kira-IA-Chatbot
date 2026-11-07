# Contexte du projet : Marketplace KIRA  - KIRA IA Chatbot Vendeur

KIRA est une application mobile marketplace permettant aux utilisateurs de vendre ou louer des biens, développée en Flutter. Elle facilite la publication d’annonces pour divers produits et services. Actuellement, le projet se concentre sur la sous-catégorie des véhicules, mais à terme, il prévoit de s'étendre à d'autres catégories telles que l'immobilier, les services, l'électronique, les vêtements, et bien plus encore.

## Pourquoi un chatbot IA pour l'optimisation des annonces ?

Pour maximiser les chances de succès des annonces et les rendre plus efficaces, l’assistant IA de vente joue un rôle clé. Il accompagne l'utilisateur tout au long du processus de création d'annonce en optimisant en temps réel les titres et descriptions, en évitant les erreurs fréquentes comme les prix exagérés ou les titres flous, et en fournissant des suggestions pertinentes basées sur des données locales. L'assistant propose également des conseils personnalisés et contextuels, afin d'améliorer chaque annonce selon le cas spécifique de l'utilisateur.

## Modèle actuel et évolution

Bien que KIRA soit une marketplace générale, le chatbot IA se concentre pour l'instant sur la vente de véhicules. Il aide les utilisateurs à remplir automatiquement les champs de leur annonce (marque, modèle, kilométrage, etc.) à travers un flux interactif. Ce modèle, développé pour la sous-catégorie des véhicules, est pensé pour être évolutif et pourra être étendu aux autres catégories de produits et services de la marketplace KIRA à l'avenir.

À long terme, ce modèle sera répliqué et adapté à diverses catégories comme l'immobilier, les services, l'électronique, et plus encore, afin de maximiser la performance des annonces sur l’ensemble de la plateforme KIRA.

Ce texte introduit le projet KIRA et met en évidence la nécessité du chatbot IA pour optimiser les annonces tout en anticipant son évolution vers d'autres catégories à l'avenir.

## Technologies utilisées 

| Élément                       | Outil / Langage                        | Rôle 💻                                                   |
|-------------------------------|----------------------------------------|----------------------------------------------------------|
| **Langage principal**          | Python 3.10+                           | Développement du service IA                              |
| **Framework API**              | FastAPI                                | Création des endpoints REST                              |
| **Serveur local**              | Uvicorn                                | Lancement du serveur web                                 |
| **IA/NLP**                     | spaCy, Transformers, Mistral (7B)      | Analyse de texte et génération de titres/descriptions    |
| **Test API**                   | Postman, Swagger UI                   | Test des échanges avec le chatbot (via Swagger UI)       |
| **Gestion de versions**        | Git                                    | Versionnement du projet                                  |
| **Gestion des environnements** | Docker, Poetry                         | Gestion des environnements et dépendances                |
| **Documentation**              | Sphinx, Markdown                       | Documentation technique et de projet (via README.md)     |

## Installation 🚀

### Prérequis

Avant de commencer, assurez-vous que vous avez installé les outils suivants :
- Python 3.10+
- Git
- Docker (optionnel, pour le déploiement)

### Cloner le repository

1. Clonez ce projet :
    ```bash
    git clone https://github.com/Bilel2010/Kira-IA-Chatbot-Vendeur-v2.git
    cd Kira-IA-Chatbot-Vendeur-v2
    ```

2. Installez les dépendances :
    ```bash
    pip install -r requirements.txt
    ```

## Exécution du projet

Pour démarrer l’application localement, utilisez cette commande :

```bash
uvicorn app.main:app --reload



## 1. Arborescence des API et test (avec Swagger/Postman) :

1.1. Santé de l'application (Health Check)

Méthode HTTP : GET

Route : /healthz

Description : Cette route permet de vérifier si le service est en ligne et fonctionne correctement. Elle retourne un statut indiquant si l'API est saine, ce qui permet de s'assurer que l'API est accessible et prête à répondre aux requêtes.

Exemple de réponse :

{
  "ok": true,
  "service": "kira-seller-bot",
  "version": "1.0.0",
  "llm_provider": "llama_cpp_local",
  "llama_model_path": "./models/mistral-7b-instruct-v0.1.Q4_K_M.gguf"
}

1.2. Catalogue

Méthode HTTP : GET

Route : /api/v1/catalog

Description : Cette route permet de récupérer la liste des catégories disponibles dans la marketplace KIRA. Elle permet à l'utilisateur de voir les différentes catégories de produits/services qu'il peut sélectionner lors de la création d'une annonce.

Exemple de réponse :

{
  "version": "1.0.0",
  "type_filter": "Vente",
  "category_filter": "Véhicules & Transport",
  "categories": [
    {
      "id": "vehicules-transport",
      "label": "Véhicules & Transport",
      "subcategories": [
        {
          "id": "voitures",
          "label": "Voitures"
        },
        {
          "id": "motos-scooters",
          "label": "Motos & scooters"
        },
        {
          "id": "velos-trottinettes",
          "label": "Vélos & trottinettes"
        }
      ]
    }
  ]
}


1.3. Sélection de la catégorie

Méthode HTTP : POST

Route : /api/v1/publish/select-category

Description : Cette API permet à l'utilisateur de sélectionner une catégorie pour son annonce. Une fois la catégorie choisie, le système initie la collecte des informations nécessaires pour l'annonce, comme la marque, le modèle, etc.

Paramètres du corps de la requête :

{
  "category_id": "vehicules-transport",
  "subcategory_id": "voitures",
  "locale": "fr",
  "attributes_mode": "chatbot"
}


Exemple de réponse :

{
  "message": "Category selected successfully. Please provide the required details."
}


1.4. Attributs de l'annonce

Méthode HTTP : POST

Route : /api/v1/publish/attributes

Description : Cette API permet de soumettre les réponses aux différents attributs de l'annonce. Les utilisateurs peuvent envoyer des informations telles que la marque, le modèle, le prix, le kilométrage, etc.

Paramètres du corps de la requête :

{
  "marque": "Toyota",
  "modele": "Corolla",
  "prix": 15000,
  "kilometrage": 120000
}


Exemple de réponse :

{
  "message": "Attributes saved successfully. Proceed to the next step."
}


1.5. Flux de publication
1.5.1. Démarrer le flux

Méthode HTTP : POST

Route : /api/v1/publish/flow/start

Description : Cette route démarre un nouveau flux pour la création de l'annonce. Cela initialise le processus de collecte d'informations, comme la sélection de la catégorie et les détails de l'annonce.

Exemple de réponse :

{
  "message": "Flow started successfully. Please select your category."
}

1.5.2. Répondre au flux

Méthode HTTP : POST

Route : /api/v1/publish/flow/reply

Description : Cette API permet de répondre aux différentes étapes du flux de publication. L'utilisateur avance dans la création de son annonce en répondant aux questions.

Paramètres du corps de la requête :

{
  "response": "Toyota"
}


Exemple de réponse :

{
  "message": "Response recorded. Proceed to the next question."
}

1.5.3. Réinitialiser le flux

Méthode HTTP : POST

Route : /api/v1/publish/flow/reset

Description : Cette route réinitialise le flux de publication. Elle permet à l'utilisateur de recommencer le processus de création d'annonce depuis le début, en supprimant toutes les réponses précédemment enregistrées.

Exemple de réponse :

{
  "ok": true,
  "message": "flow session cleared"
}

Ce guide vous permet de tester le flux complet de publication d'annonces via l'API. Vous pouvez utiliser Swagger, Postman ou pytest pour tester les différents endpoints et valider que l'application fonctionne comme prévu.

## 2. Tests et Validation de l'API

### Tester l'API avec Postman/Swagger

1. Démarrez l'application localement avec `uvicorn` :
   ```bash
   uvicorn app.main:app --reload
Accédez à Swagger UI pour tester les API :

Ouvrez votre navigateur et allez à http://localhost:8000/docs.

Utilisez Postman ou Swagger pour tester les différentes routes comme /healthz, /api/v1/catalog, etc
## 1.1 Flux de publication

1.1.1. **Démarrer le flux**  
Démarre un nouveau flux pour la création de l'annonce. Cela initialise le processus de collecte d'informations, comme la sélection de la catégorie et les détails de l'annonce.

1.1.2. **Répondre au flux**  
Permet à l'utilisateur de répondre aux différentes étapes du flux de publication. L'utilisateur avance dans la création de son annonce en répondant aux questions.

1.1.3. **Génération automatique des titres et descriptions**  
Une fois que les informations nécessaires sont collectées, le modèle **Mistral 7B Instruct** génère automatiquement le titre et la description de l'annonce, en utilisant les données d'entrée fournies par l'utilisateur. Ce processus se fait de manière autonome, permettant de gagner du temps et de maximiser la qualité des annonces.

1.1.4. **Réinitialiser le flux**  
Réinitialise le flux de publication, permettant à l'utilisateur de recommencer le processus de création d'annonce depuis le début.


## 3. Arborescence et Description des Fichiers

C:.
│   .env                    # Contient les variables d'environnement pour la configuration.
│   .gitignore               # Fichier de configuration pour ignorer les fichiers ou dossiers à ne pas versionner.
│   README.md                # Fichier de documentation expliquant le projet, les configurations, et les étapes de mise en œuvre.
│   requirements.txt         # Liste des dépendances Python nécessaires à l'exécution du projet.
│   run.py                   # Point d'entrée pour lancer l'application FastAPI.
│
├───app
│   │   main.py              # Point d'entrée principal pour l'application FastAPI, initialise les routes et le serveur.
│   │
│   ├───attributes
│   │   │   attributes.json  # Fichier JSON contenant les attributs disponibles pour les annonces.
│   │   │   engine.py        # Logiciel de traitement et d'analyse des attributs pour la création des annonces.
│   │   └───__pycache__      # Dossier contenant les fichiers compilés Python pour améliorer les performances.
│   │
│   ├───core
│   │   │   config.py        # Contient la configuration de l'application (paramètres, variables d'environnement).
│   │   │   logging.py       # Logiciel de gestion des logs pour traquer les erreurs et événements dans l'application.
│   │   └───__pycache__      # Dossier contenant les fichiers compilés Python pour améliorer les performances.
│   │
│   ├───flows
│   │   │   engine.py        # Contient la logique métier pour gérer le flow (les étapes) de la création d'annonces.
│   │   │   publish_voitures.json  # Fichier JSON définissant les étapes et prompts du flow pour la vente de véhicules.
│   │   └───__pycache__      # Dossier contenant les fichiers compilés Python pour améliorer les performances.
│   │
│   ├───routers
│   │   │   attb.py          # Routeur gérant les attributs des annonces, comme la marque, le modèle, etc.
│   │   │   cat.py           # Routeur responsable de la gestion des catégories d'annonces (Véhicules, Électronique, etc.).
│   │   │   publish_flow.py  # Routeur gérant le flux de publication d'une annonce (sélection de catégorie, attribution des attributs, etc.).
│   │   └───__pycache__      # Dossier contenant les fichiers compilés Python pour améliorer les performances.
│   │
│   ├───schemas
│   │   │   attributes.py    # Schéma pour la validation des attributs d'annonces (par exemple marque, modèle).
│   │   │   category.py      # Schéma pour la validation des catégories d'annonces.
│   │   └───__pycache__      # Dossier contenant les fichiers compilés Python pour améliorer les performances.
│   │
│   ├───services
│   │   │   catalog_service.py  # Service qui interagit avec le catalogue des catégories disponibles.
│   │   │   generation.py       # Service qui génère le titre et la description des annonces.
│   │   │   llm_service.py      # Service qui intègre le modèle de langage Mistral pour améliorer les annonces.
│   │   │   session_store.py    # Service qui gère la session de l'utilisateur (stockage temporaire des données).
│   │   └───__pycache__        # Dossier contenant les fichiers compilés Python pour améliorer les performances.
│   │
│   └───__pycache__            # Dossier contenant les fichiers compilés Python pour améliorer les performances de l'application.
│
├───data
│       categories.json        # Fichier JSON contenant les catégories disponibles dans la marketplace.
│
└───models
        mistral-7b-instruct-v0.1.Q4_K_M.gguf  # Modèle de langage Mistral utilisé pour générer des titres et descriptions enrichis pour les annonces.
        
Cette arborescence permet une bonne séparation des responsabilités et suit le principe des microservices, où chaque service est indépendant et gère une partie spécifique de l'application (génération de texte, gestion des attributs, flux de publication, etc.). Cela permet aussi d'ajouter facilement de nouvelles fonctionnalités à l'avenir.

## 4.Conclusion et Perspectives d'Amélioration

Le projet KIRA IA Chatbot Vendeur a pour objectif de faciliter la création d'annonces sur la marketplace KIRA, en particulier pour la vente de véhicules. Actuellement, le modèle est basé sur un chatbot interactif qui guide l'utilisateur à remplir chaque champ de l'annonce. Cette approche assure une expérience fluide et structurée.

Cependant, trois scénarios d'amélioration sont envisagés pour rendre l'expérience encore plus intelligente et autonome :

1. **Modèle actuel : Chatbot interactif (champ par champ)**  
   L'utilisateur remplit chaque champ de manière guidée, avec des suggestions du chatbot pour optimiser l'annonce. Ce modèle est simple, mais peut devenir plus fluide avec les évolutions futures.

2. **Modèle hybride : Complétion automatique et détection des champs manquants**  
   Ce modèle améliore l'expérience en pré-remplissant certains champs de l'annonce, tout en détectant les champs manquants. Le chatbot complète les informations existantes et guide l'utilisateur pour les champs restants.

3. **Modèle basé sur la détection par mots-clés et classification**  
   La version la plus avancée consiste à détecter automatiquement la catégorie, la sous-catégorie et les attributs d'une annonce à partir des mots-clés saisis par l'utilisateur. Par exemple, si un utilisateur tape "Je veux vendre une Golf 6 1.4 82000 km en très bon état", le chatbot peut immédiatement extraire la marque, le modèle, et le kilométrage, et remplir automatiquement ces champs.

Ces améliorations permettront non seulement de rendre l'expérience plus rapide et intuitive, mais aussi d'élargir l'application à d'autres catégories de produits et services dans la marketplace KIRA, offrant ainsi un service de plus en plus intelligent et autonome à ses utilisateurs.
