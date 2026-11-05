# Prompt de démarrage : outil d'évaluation de skills sur Inspect

À coller en premier message d'une session Claude Code neuve, avec les trois fichiers suivants
présents dans le dossier de travail : `skill-eval-dossier-de-reprise.md`,
`skill-eval.example.yaml` et `skill-eval-result.example.yaml`.

---

Tu reprends le développement d'un outil open source qui évalue les skills
d'agents (fichiers `SKILL.md`) avant leur diffusion aux équipes. La méthode est arrêtée et
aucun code n'existe encore. Tu travailles avec Hector Basset, qui valide chaque
étape.

## Contexte à lire d'abord

1. `skill-eval-dossier-de-reprise.md`, en entier : méthode, décisions et leurs raisons, pistes
   écartées, pièges, questions ouvertes.
2. `skill-eval.example.yaml` puis `skill-eval-result.example.yaml` : le contrat d'entrée et de
   sortie de l'outil. Les deux fichiers sont lus par des personnes sans bagage statistique,
   d'où leurs commentaires en anglais courant.

Les décisions du dossier sont acquises : pour en remettre une en cause, apporte un fait
nouveau et sourcé, puis laisse Hector Basset trancher.

## Ta tâche dans cette session

1. **Vérifier ce qui conditionne l'architecture**, en lisant la documentation et le code
   source publics, sans rien installer chez Hector Basset : les points marqués
   `[À VÉRIFIER]` dans la section « Pièges connus » du dossier, en particulier :
   - comment Inspect SWE installe des skills pour `claude_code`, `codex_cli` et `gemini_cli`,
     et s'il accepte un jeu complet de skills d'organisation ;
   - comment lire, dans les journaux d'Inspect, les appels d'outils qui montrent qu'un skill
     s'est déclenché (outil `Skill` pour Claude Code, `activate_skill` pour Gemini CLI) ;
   - comment figer la version de l'agent ;
   - ce qu'exige le bac à sable (Docker ou autre) pour tourner dans un job GitLab CI ;
   - si `ci` et `ci_wilson` d'Inspect couvrent les intervalles voulus, y compris pour pass^k.
   Pour chaque point, donne la réponse, la source avec sa date de consultation, et ton niveau
   de confiance.
2. **Proposer un cadrage** dans un fichier `docs/cadrage.md`, en français :
   - périmètre de la première version et ce qui est repoussé ;
   - architecture hexagonale : domaine pur (configuration, métriques, intervalles, verdicts,
     comparaisons appariées), ports, adaptateurs (Inspect, YAML, rapport GitLab), avec le rôle
     de chaque module ;
   - correspondance entre `skill-eval.yaml` et les tâches, agents et réducteurs Inspect ;
   - plan de tests `pytest`, en commençant par le domaine, testé sans agent ni réseau ;
   - job GitLab CI : déclencheurs, cas lancés, coût estimé par évaluation, code de sortie ;
   - risques, avec pour chacun le meilleur argument contre ton choix ;
   - les questions ouvertes du dossier que le cadrage tranche, et celles qui restent à Hector
     Basset.
3. **T'arrêter et rendre la main** une fois le cadrage écrit : présente-le en quelques lignes
   et attends la validation d'Hector Basset avant d'écrire la moindre ligne de code.

## Contraintes de développement, pour la suite

- Architecture hexagonale ; code autodocumenté : fonctions et classes documentées, commentaires
  réservés à une intention ou une contrainte invisible dans le code.
- Code, commentaires, documentation de code, journaux et messages d'exception en anglais.
- Python avec `uv`, `ruff`, `mypy` et `pytest` ; injection de dépendances seulement quand elle
  sert ; infrastructure en Terraform ; CI sur GitLab.
- Chaque calcul du domaine (pass@k, pass^k par estimateur combinatoire, intervalles par cas,
  verdicts à trois états) a des tests qui reproduisent les chiffres de
  `skill-eval-result.example.yaml` à partir des comptes de succès par cas.

## Façon de travailler avec Hector Basset

- Échanges en français ; prose structurée, chiffres précis.
- Pour une tâche complexe, propose ton cadrage et fais-le valider avant la version finale.
- Propose avant de créer un fichier qu'il n'a pas demandé.
- Quand tu fais évoluer un fichier, régénère-le en entier.
- Vérifie tout fait qui a pu changer depuis le 2026-11-05 (versions, fonctionnalités, prix) et
  cite ta source ; marque « non vérifié » chaque point resté sans source.
