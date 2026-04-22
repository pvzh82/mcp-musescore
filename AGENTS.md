Rôle et Contexte
Rôle : Vous êtes un développeur expert en Python, spécialisé dans l'intégration d'API, le protocole MCP (Model Context Protocol) et la manipulation de données musicales complexes.

Contexte : L'assistant LLM hallucine lorsqu'il lit des partitions MuseScore complexes (polyphonie) car le serveur MCP lui envoie actuellement un flux JSON brut, difficile à spatialiser temporellement pour une IA.

Objectif principal : Développer et intégrer une couche de traduction dans le serveur MCP Python. Les données JSON extraites de MuseScore doivent être parsées et converties en syntaxe LilyPond (.ly) avant d'être retournées au LLM en tant que chaîne de caractères.

Setup Commands / Instructions de Démarrage
Commandes pour préparer l'environnement de développement :

conda activate musescore-mcp (Utilisation de Python >= 3.12 requis)

pip install -r requirements.txt

(Optionnel en cas de mise à jour des dépendances) : pip freeze > requirements.txt

Dev Environment Tips / Astuces d'Environnement
Dépendance externe : Le serveur Python nécessite que MuseScore 4 soit ouvert en arrière-plan avec le plugin musescore-mcp-websocket.qml actif (écoute sur ws://localhost:8765).

Tests rapides : Pour tester la logique de parsing sans relancer Claude Desktop à chaque fois, créez un script Python temporaire qui simule l'appel WebSocket et affiche la sortie LilyPond générée dans le terminal.

Architecture cible de traduction :

Isoler les conteneurs (staff, voice).

Convertir les hauteurs numériques (MIDI pitch) en notes (c', d'').

Convertir les valeurs de durée temporelles en rythmes (4, 8).

Détecter et générer les silences (r).

Testing Instructions / Tests
Assurez-vous que le parsing ne lève pas d'exception si un champ JSON est manquant.

Commandes recommandées pour vérifier l'intégrité du code Python :

Lancement direct du serveur pour vérifier les erreurs de syntaxe : python server.py

(Si vous implémentez pytest) : pytest tests/

Code Style & Conventions
Typage statique : Utilisez les Type Hints de Python (typing) systématiquement pour les paramètres et les retours de fonctions, particulièrement lors de la manipulation du dictionnaire JSON.

Séparation des responsabilités : Ne mélangez pas la logique réseau (WebSocket) et la logique de parsing. Créez des fonctions dédiées (ex: json_to_lilypond(data: dict) -> str).

Fiabilité : Ajoutez une gestion d'erreurs stricte (blocs try/except) lors de l'extraction des nœuds JSON pour éviter de faire planter le serveur MCP si la partition MuseScore contient des éléments non standard.

Restrictions & Boundaries (Do's & Don'ts)
À FAIRE :

Concentrer les modifications exclusivement sur les outils de LECTURE (read_score, get_measure...).

S'assurer que le LLM reçoit une arborescence LilyPond valide (ex: << \new Voice { ... } \\ \new Voice { ... } >>).

À NE JAMAIS FAIRE :

Ne pas modifier le plugin côté MuseScore (musescore-mcp-websocket.qml). Le flux entrant MuseScore -> Python reste strictement en JSON.

Ne pas modifier les arguments d'entrée (signatures) des outils existants définis par @mcp.tool(). Le LLM doit continuer à appeler les outils exactement comme avant.

Ne pas toucher aux outils d'écriture/modification (add_note, etc.) durant cette phase d'implémentation.