---
titre: "Outil d'évaluation de skills d'agents sur Inspect : dossier de reprise"
genre: dossier-de-reprise
statut: brouillon
date_redaction: 2026-11-05
faits_arretes_au: 2026-11-05
prochaine_revue: 2027-02-05
auteur: "Hector Basset, rédigé avec Claude"
lectorat: >
  Développeuse ou développeur Python, humain ou IA en session neuve, qui connaît les skills
  d'agents (fichier SKILL.md, déclenchement par la description), Claude Code et les
  évaluations de LLM en général, mais n'a pas suivi les échanges du 2026-11-03 au 2026-11-05
  qui ont fixé la méthode.
perimetre: >
  Couvre la méthode d'évaluation retenue (métriques, calculs, verdicts), le format de
  configuration et de résultat, le choix du moteur Inspect, les contraintes de développement
  et les décisions encore ouvertes. Ne couvre ni le code (rien n'est écrit), ni la rédaction
  des cas de test d'un skill donné.
usage_prevu: >
  Démarrer le développement d'un outil open source ou d'un job CI qui évalue des skills
  d'agents, en commençant par un cadrage à faire valider par Hector Basset.
sources: [S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12, S13, S14, S15, S16, S17, S18, S19]
statut_epistemique: >
  Méthode arrêtée en échange (S1) ; faits sur les outils lus dans leur documentation
  officielle le 2026-11-05 ; aucun outil installé ni testé ; chiffres d'exemple fictifs.
---

# Outil d'évaluation de skills d'agents sur Inspect : dossier de reprise

## Résumé

Au 2026-11-05, la méthode d'évaluation de skills d'agents est arrêtée et
aucun code n'est écrit. L'outil mesure séparément l'invocation (le skill se déclenche-t-il
quand il le doit, et seulement alors) et la qualité (une fois lancé, fait-il bien le travail),
répète chaque cas, calcule pass@1, pass@k et pass^k avec des intervalles regroupés par cas, et
rend un verdict à trois états (réussi, échoué, indécis). Moteur retenu : Inspect et Inspect SWE,
sous une couche mince maison. Configuration et résultat d'exemple : `skill-eval.example.yaml`
et `skill-eval-result.example.yaml`, livrés avec ce dossier. Prochaine étape : proposer un
cadrage d'architecture et le faire valider par Hector Basset avant de coder. Lire d'abord
« Où en est le travail », « Métriques et calculs » et « Prochaines étapes », puis les YAML.

Sauf mention contraire, les décisions viennent de l'échange S1 et les faits sur les outils de
leur documentation citée.

## Glossaire de l'évaluation de skills

- **Skill** : dossier d'instructions au format Agent Skills (fichier `SKILL.md` avec un nom et
  une description) qu'un agent charge quand la description correspond à la demande [S11].
- **Cas positif / cas négatif** : demande où le skill doit se déclencher / demande proche du
  sujet où il ne doit pas se déclencher (« near miss » dans [S11]).
- **Essai** (*trial*) : une exécution d'un cas dans une conversation neuve.
- **pass@1** : taux de réussite d'un essai. **pass@k** : probabilité qu'au moins un essai sur k
  réussisse. **pass^k** (lu « pass hat k ») : probabilité que k essais de suite réussissent
  tous [S2] [S3].
- **Rappel** : part des essais sur cas positifs où le skill s'est déclenché.
- **Taux de déclenchements à tort** : part des essais sur cas négatifs où le skill s'est
  déclenché.
- **Précision** : part des déclenchements justifiés ; dépend de la proportion de cas positifs.
- **Cas réservés** (*holdout*) : cas mis de côté, jamais utilisés pour retoucher le skill ; seuls
  eux décident du verdict.
- **Juge** : modèle qui note une sortie quand une règle automatique ne suffit pas.
- **Kappa de Cohen** : accord entre deux notateurs, corrigé du hasard.
- **Écart avec et sans skill** (*lift*) : différence de qualité, cas par cas, entre essais avec
  le skill et essais sans lui.
- **Inspect** : framework Python d'évaluation de LLM créé par l'institut britannique de sécurité
  de l'IA (UK AI Security Institute) [S7]. **Inspect SWE** (SWE pour *software engineering*) :
  extension qui pilote des agents de code dans un bac à sable : Claude Code, Codex CLI, Gemini
  CLI, Kimi Code, OpenCode et mini-SWE-agent [S5].

## Pourquoi ce document existe

Hector Basset a construit avec Claude, du
2026-11-03 au 2026-11-05, une méthode [S1] pour évaluer les skills diffusés aux équipes avant de les
partager. Le développement de l'outil se fera dans une session neuve, sans accès à cet échange.
Ce dossier en fige l'état ; il ne remplace aucun document existant.

## Périmètre et hors-périmètre

Dans le périmètre : la méthode, les fichiers d'exemple, le choix d'outil, les contraintes de
développement, les décisions ouvertes.

Hors périmètre, exclu délibérément : le code de l'outil ; les cas de test d'un skill donné ;
l'infrastructure des runners GitLab (non examinée) ; l'instrumentation par hooks de l'usage
réel, évoquée seulement comme source de cas (section « Questions ouvertes »).

## Où en est le travail

- Fait : méthode et métriques arrêtées (section « Métriques et calculs ») ; format de
  configuration et de résultat arrêté (deux fichiers YAML livrés avec ce dossier, valides en
  YAML) ; moteur choisi (section « Ce qui a été décidé et pourquoi »).
- Pas fait : dépôt Git, code, tests, job CI, cas de test d'un premier skill pilote.
- Hector Basset a dit le 2026-11-05 suivre toutes les recommandations de méthode listées dans
  ce dossier ; les valeurs numériques marquées comme valeurs de départ restent à confirmer.

## Vérifier l'état avant d'agir

1. Ouvrir les deux fichiers YAML et vérifier qu'ils se chargent (`yaml.safe_load`).
2. Revérifier les faits datés du 2026-11-05 qui conditionnent l'architecture, marqués
   `[À VÉRIFIER]` dans « Pièges connus » : versions d'Inspect et d'Inspect SWE, support des
   skills par agent, bac à sable Docker dans GitLab CI.
3. Critère de fin du chantier, première version : sur un skill pilote, `skill-eval.yaml` en
   entrée produit un fichier conforme à `skill-eval-result.example.yaml`, localement et dans un
   job GitLab CI dont le code de sortie suit le verdict.

## Métriques et calculs

Tout ce qui suit vient de l'échange [S1], sauf les définitions sourcées.

**Par cas, puis moyenne sur les cas.** Pour un cas exécuté n fois avec c succès :
pass@k = 1 − C(n−c, k) / C(n, k) et pass^k = C(c, k) / C(n, k) [S3]. Chaque métrique est la
moyenne des valeurs par cas. Appliquer la formule p^k à un taux moyen est faux quand les échecs
se concentrent sur certains cas.

**Invocation** (jeu de cas positifs et négatifs) :
- rappel = moyenne sur les cas positifs de (déclenchements / essais) ;
- taux de déclenchements à tort = moyenne sur les cas négatifs de (déclenchements / essais) ;
- précision = déclenchements justifiés / tous les déclenchements, publiée sans seuil ;
- pass^k sur cas positifs (seuil) et pass^k sur cas négatifs (information).

**Qualité** (invocation toujours forcée par le préfixe `/<nom-du-skill>` ajouté par le runner) :
un essai réussit seulement si toutes ses vérifications passent ; pass@1 (seuil), pass@k
(diagnostic, sans seuil), pass^k (seuil) et la courbe de pass^k pour k de 1 à n.

**Intervalles.** Calculés sur les valeurs par cas, parce que les essais d'un même cas ne sont
pas indépendants : intervalle de Student à (nombre de cas − 1) degrés de liberté, borné à
[0, 1] ; intervalle de Wilson quand tous les cas ont la même valeur. Inspect fournit
`stderr(cluster=...)`, `ci` et `ci_wilson` [S4].

**Verdict par seuil.** Cinq seuils, calculés sur les cas réservés seulement :
`invocation_recall` (minimum), `invocation_false_trigger_rate` (maximum),
`invocation_pass_hat_k` sur cas positifs (minimum), `quality_pass_at_1` (minimum) et
`quality_pass_hat_k` (minimum). Seuil minimum : réussi si la borne basse l'atteint, échoué si la borne
haute reste en dessous, indécis sinon. Seuil maximum (taux de déclenchements à tort) :
symétrique. Sous `minimum_cases` cas réservés, verdict indécis. Le skill est diffusable
seulement si tous les seuils sont réussis.

**Comparaisons appariées.** L'écart avec et sans skill et la comparaison avec la version
précédente se calculent par différence cas par cas sur les mêmes cas réservés, avec un
intervalle de Student [S14].

## Ce qui a été décidé et pourquoi

| Décision | Raison |
|---|---|
| Couche mince sur Inspect + Inspect SWE, sans exécuteur propre | L'exécution isolée d'agents existe déjà ; Inspect fournit `pass_k_{k}`, `pass_at_{k}`, l'erreur type groupée et des intervalles [S4], et pilote Claude Code, Codex CLI et Gemini CLI [S5] |
| Usage visé : outil en ligne de commande ou job CI | Choix d'Hector Basset, 2026-11-05 |
| Seuil sur le taux de déclenchements à tort, pas sur la précision | Avec rappel 0,90 et 3 % de déclenchements à tort, la précision vaut 0,97 sur un jeu équilibré et 0,77 si 10 % des demandes réelles concernent le skill |
| Seuil pass^k d'invocation sur les cas positifs seuls | Le chiffre global dépend de la proportion de cas positifs |
| F-bêta supprimé | L'asymétrie entre oubli et déclenchement à tort se règle par les valeurs des seuils |
| 10 essais par cas, k = 3 pour pass@k, k = 5 pour pass^k, communs aux deux volets | Avec n = k, pass^k d'un cas vaut 0 ou 1 ; n ≥ 2k donne une estimation graduée |
| Cas réservés (40 %), verdict sur eux seuls | Éviter le surajustement de la description aux cas qui jugent [S11] |
| Invocation évaluée avec tous les skills de l'organisation installés, version de l'agent figée | Claude Code limite la liste des descriptions à 1 % de la fenêtre de contexte et retire d'abord celles des skills les moins utilisés [S8] |
| Juge calibré sur des réponses notées par une personne (kappa) ; vérifications déterministes d'abord | L'accord brut surestime l'accord réel [S16] ; un juge qui rejette à tort 5 % des bonnes réponses plafonne pass^5 à 0,77 |
| Écart avec et sans skill mesuré, sans seuil | Mesure centrale de `claude plugin eval` [S9] et de l'approche ACES (Agentic Continuous Evaluation of Skills) de NVIDIA [S18] |
| Intervalles de Student ou Wilson, pas de bootstrap percentile | Avec 5 à 30 grappes, les tests standards rejettent à tort environ 10 % du temps au lieu de 5 % [S15] ; le bootstrap percentile dégénère quand beaucoup de cas sont à 100 % |
| Configuration lisible par des personnes sans bagage statistique | Les équipes qui écrivent les cas ne sont pas data scientists ; commentaires en anglais courant, sans jargon statistique |
| Pas de vérification informative en qualité en première version | Choix d'Hector Basset : toutes les vérifications comptent |

## Ce qui a été essayé et écarté

- **Vally** (`@microsoft/vally-cli`, version 0.21) : le plus pensé pour les skills (grader
  `skill-invocation`, `vally lint`, GitHub Actions), mais l'exécuteur par défaut est Copilot,
  sans intervalles de confiance [S12]. Option à rouvrir si Copilot devient une cible.
- **`claude plugin eval`** : officiel et prêt pour la CI, mais limité à Claude Code et à des
  skills livrés en plugin ; ne nomme ni pass@k ni pass^k [S9]. Reste la voie de repli.
- **promptfoo** : assertions `skill-used` et `not-skill-used`, `--repeat`, mais ni Gemini CLI
  ni pass^k [S13].
- **skill-creator** (Anthropic) : boucle d'optimisation de la description, faite pour itérer
  en conversation, pas pour la CI ; des signalements font état d'un rappel mesuré à 0 % à cause
  du harnais [S19].
- **NVIDIA SkillEvaluator** (préprint ACES) : expérimental, ni déclenchement ni pass^k [S18].
- Abandonnés dans la méthode : `beta` et F-bêta, `pass_hat_k_scope`, seuil sur la précision,
  seuil pass^k d'invocation sur tous les cas, bootstrap percentile, `run_success` configurable,
  vérifications informatives.

## Prochaines étapes

1. Revérifier les points `[À VÉRIFIER]` de « Pièges connus » (session de développement).
2. Proposer un cadrage : périmètre de la première version, architecture hexagonale, plan de
   tests, job GitLab CI, coût estimé par évaluation ; le faire valider par Hector Basset.
3. Choisir un skill pilote et écrire ses cas (au moins 38 cas d'invocation de chaque sorte et
   38 cas de qualité pour atteindre 15 cas réservés) : porteur `[LACUNE]`.
4. Développer, puis valider sur le skill pilote contre le critère de fin.

## Contraintes de développement

Préférences déclarées par Hector Basset : architecture hexagonale ; code autodocumenté
(commentaires seulement si nécessaires, fonctions et classes documentées) ; code, commentaires,
documentation de code, journaux et messages d'exception en anglais ; outillage Python `uv`,
`ruff`, `mypy`, `pytest` ; injection de dépendances seulement si nécessaire ; infrastructure en
Terraform ; CI sur GitLab. Méthode de travail : proposer le cadrage d'une tâche complexe et le
faire valider avant la version finale ; proposer avant de créer un fichier non demandé ;
régénérer un fichier en entier à chaque itération ; échanges en français.

`[OPINION]` Découpage hexagonal de départ, à discuter au cadrage : un domaine pur (modèle de
configuration, calcul des métriques, intervalles, verdicts, comparaisons) testé sans agent ;
des ports pour l'exécution des essais, la lecture de la configuration, le stockage des
résultats et le rapport ; des adaptateurs Inspect, YAML et GitLab (rapport de merge request).

## Pièges connus

- **Liste des skills tronquée** : dans Claude Code, avec de nombreux skills installés, des
  descriptions disparaissent de la liste chargée en contexte [S8]. Un skill évalué seul
  se déclenche mieux qu'en mission.
- **Détection de l'invocation dans Claude Code** : appel de l'outil `Skill`, champ
  `tool_input.skill`, forme préfixée `plugin:skill` possible [S9] [S10]. Une commande `/skill`
  tapée passe par l'événement `UserPromptExpansion`, pas par l'outil `Skill` [S10] : en
  qualité, l'invocation forcée ne se détecte donc pas comme une invocation autonome.
- **Détection dans Gemini CLI** : outil `activate_skill`, argument `name` ; une confirmation
  est demandée à l'activation, à approuver automatiquement en mode non interactif [S17].
- **Harnais muet** : un rappel à 0 % peut venir du harnais [S19]. Inclure un cas témoin qui
  nomme explicitement le skill et doit toujours le déclencher.
- **Nom de skill** : minuscules, chiffres et tirets seulement, identique au nom du dossier [S11].
- `[À VÉRIFIER]` Support des skills par Inspect SWE : annoncé pour Claude Code et Codex CLI
  (version 0.2.30, 2025-12-24), utilisé avec Gemini CLI dans un tutoriel Google [S5] [S6] ;
  installation d'un jeu complet de skills d'organisation non documentée.
- `[À VÉRIFIER]` Bac à sable : Inspect SWE fait tourner l'agent dans le bac à sable de
  l'échantillon, Docker dans les exemples [S5] ; capacité des runners CI inconnue.
- `[À VÉRIFIER]` Versions au 2026-11-05 : `inspect-ai` 0.3.287 (licence MIT, statut Beta) [S7],
  `inspect-swe` 0.2.67 [S5]. Gemini CLI remplacé par Antigravity CLI pour les comptes gratuits
  depuis le 2026-06-18, selon une mention de sa documentation [S17].
- **Coût** : par évaluation, environ 1 000 essais d'invocation courts (100 cas, 10 essais) et
  380 essais de qualité complets, doublés si l'écart avec et sans skill est mesuré. Chiffre
  calculé sur l'exemple, coût réel non mesuré.

## Emplacements

- Fichiers livrés le 2026-11-05 avec ce dossier : `skill-eval.example.yaml` (configuration) et
  `skill-eval-result.example.yaml` (résultat), à ranger dans `docs/` du futur dépôt.
- Dépôt de l'outil : `[LACUNE]`, non créé au 2026-11-05.
- Arborescence des cas prévue : `evals/invocation/positive/`, `evals/invocation/negative/`,
  `evals/quality/`, `evals/quality/judge-calibration/`.

## Ce qui n'est qu'une hypothèse

- `[HYPOTHÈSE]` Valeurs de départ à confirmer sur le skill pilote : `minimum_cases: 15`,
  `judge_minimum_agreement: 0.60`, `holdout_share: 0.4`, et les valeurs de seuil d'exemple.
- `[HYPOTHÈSE]` Le découpage des cas réservés par nom de cas reste stable quand on ajoute des cas.
- `[INFÉRENCE]` Les fonctions `ci` et `ci_wilson` d'Inspect couvrent les intervalles voulus ;
  à confirmer pour pass^k, qui n'est pas une proportion d'essais.
- `[INFÉRENCE]` Les chiffres de l'exemple de résultat sont fictifs, calculés pour être cohérents
  entre eux ; ils ne décrivent aucun skill réel.

## Questions ouvertes

| Question | Qui tranche |
|---|---|
| Agents couverts en première version : Claude Code seul, ou aussi Codex CLI, Gemini CLI, GitHub Copilot ? | Hector Basset |
| Les runners CI peuvent-ils lancer des conteneurs Docker pour le bac à sable ? | Personne qui administre les runners `[LACUNE]` |
| Où stocker les résultats de référence pour comparer deux versions (artefact du pipeline principal, dépôt) ? | Cadrage |
| Le job de merge request lance-t-il seulement les cas réservés, pour limiter le coût ? | Cadrage |
| Deux niveaux d'exigence selon le risque du skill (skills de confort, skills qui agissent) ? | Hector Basset, après le pilote |
| Collecter des demandes réelles par hooks pour écrire les cas : conformité RGPD ? | Hector Basset et la personne déléguée à la protection des données `[LACUNE]` |
| Formule exacte de pass^k dans Vally (p^k appliqué au taux moyen, ou estimateur combinatoire) | Non bloquant, à vérifier si Vally est rouvert |

## Sources

- **S1** : échange entre Hector Basset et Claude, 2026-11-03 au 2026-11-05, conversation claude.ai non partagée, échange privé.
- **S2** : « Demystifying evals for AI agents », Anthropic, 2026-01-09, https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents, communication d'éditeur, consulté le 2026-11-03.
- **S3** : Yao et al., « τ-bench », arXiv 2406.12045, 2024, https://arxiv.org/html/2406.12045v1, préprint, consulté le 2026-11-03.
- **S4** : « Scoring Metrics », documentation Inspect, https://inspect.aisi.org.uk/metrics.html, documentation officielle, consultée le 2026-11-05.
- **S5** : documentation et changelog Inspect SWE, Meridian Labs, https://meridianlabs-ai.github.io/inspect_swe, documentation officielle, consultée le 2026-11-05.
- **S6** : « Evaluate agent skills using open source frameworks », Google Codelabs, https://codelabs.developers.google.com/codelabs/evaluate-agent-skills-using-open-source-frameworks, tutoriel d'éditeur, consulté le 2026-11-05.
- **S7** : page PyPI `inspect-ai`, https://pypi.org/project/inspect-ai/, page de version, consultée le 2026-11-05.
- **S8** : « Extend Claude with skills », documentation Claude Code, https://code.claude.com/docs/en/skills.md, documentation officielle, consultée le 2026-11-05.
- **S9** : « Test plugins with evals », documentation Claude Code, https://code.claude.com/docs/en/plugin-evals, documentation officielle, consultée le 2026-11-03.
- **S10** : « Hooks reference », documentation Claude Code, https://code.claude.com/docs/en/hooks, documentation officielle, consultée le 2026-11-03.
- **S11** : « Optimizing skill descriptions » et « Specification », Agent Skills, https://agentskills.io/skill-creation/optimizing-descriptions, documentation du standard, consultée le 2026-11-05.
- **S12** : documentation Vally, https://microsoft.github.io/vally/, documentation officielle, consultée le 2026-11-05.
- **S13** : « Test agent skills », documentation promptfoo, https://www.promptfoo.dev/docs/guides/test-agent-skills/, documentation officielle, consultée le 2026-11-05.
- **S14** : Miller, « Adding Error Bars to Evals », arXiv 2411.00640, 2024, https://arxiv.org/html/2411.00640v1, préprint non relu par les pairs, consulté le 2026-11-03.
- **S15** : Cameron, Gelbach et Miller, « Bootstrap-Based Improvements for Inference with Clustered Errors », Review of Economics and Statistics, 2008, https://econpapers.repec.org/RePEc:tpr:restat:v:90:y:2008:i:3:p:414-427, article relu (résumé seul consulté), 2026-11-05.
- **S16** : Norman et al., « Reliability without Validity », arXiv 2606.19544, 2026, https://arxiv.org/html/2606.19544, préprint non relu par les pairs, consulté le 2026-11-05.
- **S17** : documentation Gemini CLI (hooks, outil `activate_skill`, evals comportementales), https://geminicli.com/docs/hooks/, documentation officielle, consultée le 2026-11-03 et le 2026-11-05.
- **S18** : NVIDIA SkillEvaluator, https://github.com/NVIDIA/SkillEvaluator, et préprint ACES, arXiv 2608.20614, https://arxiv.org/abs/2608.20614, dépôt et préprint, consultés le 2026-11-05.
- **S19** : signalements sur le harnais de skill-creator, site miroir des issues Claude Code, https://claudeissues.com/issue/36570-claude-p-does-not-trigger-skills-skill-creator-eval-loop-always-shows-0-recall, source secondaire non vérifiée sur GitHub, consultée le 2026-11-05.
