# Cadrage de la première version

Faits arrêtés au 2026-11-05. Ce document répond aux points `[À VÉRIFIER]` du dossier de reprise
(`docs/reprise/skill-eval-dossier-de-reprise.md`), propose le périmètre et l'architecture de la
première version, et liste ce qui reste à trancher. Les décisions de méthode du dossier sont
reprises telles quelles. Quand l'implémentation ou la vérification a révélé un problème, il est
signalé ici et détaillé dans une issue, sans être tranché à la place d'Hector Basset.

Étiquettes de confiance : [Établi] pour un fait lu à sa source primaire (code source, page de
version, documentation officielle sur ses propres spécifications), [Fragile] pour un fait à
confirmer par un essai réel, [Sans source fiable] quand rien n'a été trouvé.

## 1. Points vérifiés

Les sources de code sont les paquets publiés `inspect-ai` 0.3.287 et `inspect-swe` 0.2.72,
installés dans un environnement jetable le 2026-11-05, hors du poste d'Hector Basset.

### Versions

`inspect-ai` 0.3.287 est bien la dernière version (PyPI, publiée le 2026-10-31) [Établi].
`inspect-swe` est en 0.2.72 (PyPI et étiquette GitHub, publiée le 2026-10-20), pas en 0.2.67
comme l'indique le dossier [Établi]. Inspect SWE 0.2.72 pilote aussi `antigravity`, ce qui
compte puisque la documentation de Gemini CLI annonce que « Gemini CLI was replaced by
Antigravity CLI on June 18th, 2026 » pour les comptes gratuits et Google One (bandeau de
geminicli.com, consulté le 2026-11-05) [Établi].

### Installation des skills par Inspect SWE

Les trois agents acceptent un paramètre `skills` (liste de dossiers) et l'installent avec
`inspect_ai.tool.install_skills` [Établi] :

| Agent | Dossier d'installation | Source (inspect-swe 0.2.72) |
|---|---|---|
| `claude_code` | `<cwd>/.claude/skills` | `_claude_code/claude_code.py`, l. 435-438 |
| `codex_cli` | `<codex_home>/skills` | `_codex_cli/codex_cli.py`, l. 539-542 |
| `gemini_cli` | `<cwd>/.gemini/skills` | `_gemini_cli/gemini_cli.py`, l. 147-150 |

Un jeu complet de skills d'organisation passe donc techniquement, en listant chaque dossier.
Mais le chargeur d'Inspect déforme ce qu'il installe, ce que le dossier n'avait pas vu
(`inspect_ai/tool/_tools/_skill/read.py` et `types.py`) [Établi] :

- le frontmatter est validé avec `additionalProperties: false` sur `name`, `description`,
  `license`, `compatibility`, `metadata` et `allowed-tools`. Un skill qui utilise un champ propre
  à Claude Code (`when_to_use`, `disable-model-invocation`, `argument-hint`, `paths`, etc.,
  listés dans « Extend Claude with skills », consulté le 2026-11-05) fait échouer tout le
  chargement ;
- seuls `scripts/`, `references/` et `assets/` sont copiés ; un autre dossier (`meta/`) ou un
  fichier à la racine du skill disparaît ;
- `SKILL.md` est réécrit à partir du frontmatter analysé.

Or `when_to_use` compte dans le texte de déclenchement (la page skills de Claude Code plafonne
`description` et `when_to_use` réunis à 1 536 caractères). Retirer ces champs pour passer la
validation changerait donc ce qu'on mesure.

**Proposition** : ne pas utiliser `skills=`. Copier les dossiers de `installed_skills` tels quels
dans le bac à sable, au même emplacement (`<cwd>/.claude/skills` pour Claude Code), puis
calculer leur empreinte pour `installed_skills_hash`.

### Lecture des déclenchements dans les journaux

Pour Claude Code, Inspect SWE lit la sortie `stream-json` et écrit dans le transcript Inspect un
`ToolEvent` par appel d'outil, avec le nom de l'outil dans `function`, ainsi qu'un
`InfoEvent(source="skill_command", data={"skill": nom})` quand une commande `/skill` est tapée
(`_claude_code/_events/events.py`, l. 214-290 et 507-514) [Établi]. Un déclenchement autonome se
lit donc sur un `ToolEvent` dont `function` vaut `Skill`, et l'invocation forcée de la partie
qualité sur l'`InfoEvent`, ce qui confirme le piège décrit dans le dossier. Le nom du champ qui
porte le nom du skill dans les arguments (`skill`) et la forme préfixée `plugin:skill` ne
figurent pas sur la page hooks consultée le 2026-11-05 [Fragile] : le cas témoin du premier
essai réel doit les confirmer.

Pour Gemini CLI, la documentation nomme l'outil `activate_skill` et annonce une confirmation à
chaque activation (geminicli.com, pages skills, consultées le 2026-11-05) [Établi]. Le nom de
l'argument et le comportement en mode non interactif n'y figurent pas [Sans source fiable].
L'adaptateur `gemini_cli` d'Inspect SWE ne décode pas les événements de l'agent ; le
déclenchement devrait se lire dans les appels de modèle relayés par le pont d'Inspect
[Fragile].

### Version figée de l'agent

`claude_code(version="2.1.309")` télécharge cette version précise. Le binaire est téléchargé
côté hôte, vérifié par somme de contrôle, mis en cache puis copié dans le bac à sable
(`_util/agentbinary.py`) [Établi]. Le job CI a donc besoin du réseau vers la source de
téléchargement, ou d'un cache, mais pas le bac à sable. Les valeurs `auto`, `stable` et
`latest` sont refusées par la configuration.

Deux réglages de Claude Code changent le déclenchement sans changer de version : le réglage
`skillListingBudgetFraction` et la variable `SLASH_COMMAND_TOOL_CHAR_BUDGET` (page skills,
consultée le 2026-11-05) [Établi]. Inspect SWE fixe aussi des variables par défaut, dont
`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` (`_claude_code/env.py`) [Établi]. Les trois sont à figer et
à enregistrer dans `run.environment`.

`effort` n'existe que pour `claude_code` (valeurs `low`, `medium`, `high`, `xhigh`, `max`,
`_claude_code/model.py`) ; les signatures de `codex_cli` et `gemini_cli` n'ont pas ce paramètre
[Établi].

### Bac à sable en CI

Inspect SWE exige un bac à sable Linux x64 ou arm64, glibc ou musl (`_util/sandbox.py`)
[Établi]. Trois options :

- Docker, comme dans les exemples : Docker-in-Docker sur un runner privilégié, ou socket Docker
  de l'hôte ;
- Kubernetes avec `inspect-k8s-sandbox` 0.14.0 (PyPI, publiée le 2026-10-09) [Établi] ;
- le bac à sable `local` d'Inspect, à écarter : l'agent, lancé avec
  `--dangerously-skip-permissions`, partagerait le système de fichiers et les secrets du job.

Les capacités des runners restent inconnues (le dossier visait des runners GitLab, le dépôt est
sur GitHub). Que les runners GitHub hébergés fournissent Docker est non vérifié.

### `ci` et `ci_wilson` d'Inspect

`ci(method="t", cluster=...)` calcule `moyenne ± t × erreur type` avec `grappes - 1` degrés de
liberté, sans borner à [0, 1] ; `ci_wilson(cluster=...)` applique Wilson avec une taille
effective de Korn-Graubard et un quantile de Student, et revient à la taille brute quand la
proportion vaut 0 ou 1 (`inspect_ai/scorer/_metrics/std.py`, l. 172-340) [Établi]. Après
réduction des époques, une valeur par cas, `ci` donne l'intervalle de Student voulu avant
bornage ; pass^k entre dans les deux fonctions puisque ses valeurs par cas sont dans [0, 1].
Mais aucune ne fait « Student, et Wilson quand tous les cas ont la même valeur », ni les
différences appariées.

**Choix retenu** : le domaine calcule lui-même estimateurs et intervalles, à partir des comptes
de succès par cas. Une vérification croisée ponctuelle donne un écart maximal de 2,2e-16 entre
nos estimateurs et les réducteurs `pass_at` et `pass_k` d'Inspect (n de 5 à 20, tous les c,
k = 1, 2, 3, 5), et de 7,4e-13 entre le quantile de Student d'Inspect et celui de SciPy.

## 2. Périmètre de la première version

Dans la V1 :

- le domaine complet : configuration et ses règles, découpage des cas réservés, pass@k, pass^k,
  intervalles, verdicts à trois états, comparaisons appariées, kappa, diagnostics, résumé (fait,
  PR 2 à 4) ;
- la commande `report`, qui transforme un enregistrement de comptes par cas
  (`docs/skill-eval-record.example.yaml`) en fichier de résultat, avec un code de sortie qui
  suit le verdict, et la commande `check-config` (fait, PR 5) ;
- l'exécuteur Inspect pour Claude Code seul, qui produit l'enregistrement (issue) ;
- le job CI d'un skill pilote (issue).

Repoussé : Codex CLI, Gemini CLI et Antigravity ; le rapport de merge request ; Terraform, tant
que les runners ne sont pas connus ; la collecte de demandes réelles par hooks.

## 3. Architecture hexagonale

| Couche | Module | Rôle |
|---|---|---|
| Domaine | `estimators` | `CaseCount`, pass@k, pass^k, moyenne par cas |
| | `intervals` | Student par cas borné, Wilson si toutes les valeurs sont égales, différences |
| | `verdicts` | Limite minimum ou maximum, verdict sur l'intervalle entier |
| | `comparison` | Différence appariée sur les cas communs, lecture du sens |
| | `agreement` | Kappa de Cohen |
| | `config` | Réglages de `skill-eval.yaml` et leurs règles, tous les problèmes à la fois |
| | `split` | Cas réservé ou de réglage selon le SHA-256 du nom |
| | `evaluation`, `results` | Scores, seuils, garde-fous, diagnostics, résumé |
| Application | `report` | Découpe, évalue, compare, avertit ; code de sortie |
| Adaptateurs | `yaml_input` | Lecture de la configuration et des enregistrements (pydantic puis domaine) |
| | `yaml_result` | Écriture du résultat commenté du contrat |
| | `inspect_runner` (à venir) | Tâches Inspect, lecture des journaux, production de l'enregistrement |
| Entrée | `cli` | `check-config`, `report`, et plus tard `run` |

Le domaine n'importe ni fichier, ni YAML, ni pydantic, ni Inspect ; un test d'architecture le
vérifie sur les imports. Le cas d'usage `report` ne dépend d'aucun port : il reçoit des objets
du domaine et rend un rapport, et c'est la CLI qui lit et écrit les fichiers. Le premier port
apparaîtra avec l'exécuteur (`TrialRunner`), parce qu'il aura deux implémentations : Inspect,
et un faux pour les tests.

L'enregistrement de comptes par cas sert de contrat entre l'exécuteur et le rapport. Il permet
de recalculer un résultat sans relancer d'agent, et il est aussi la seule base possible pour la
comparaison avec la version précédente : le fichier de résultat ne contient pas les comptes de
tous les cas réservés.

## 4. Correspondance avec Inspect

| `skill-eval.yaml` | Inspect |
|---|---|
| un jeu de cas (`positive`, `negative`, `quality`, et sans skill si `measure_lift`) | une `Task`, un `Sample` par cas, `id` = nom du cas |
| `invocation_per_case`, `quality_per_case` | `epochs` de la tâche |
| `agent`, `agent_version`, `model`, `effort` | `claude_code(version=..., model=..., effort=...)` |
| `installed_skills` | copie des dossiers dans le bac à sable, hors `skills=` |
| `invocation.max_turns` | pas de paramètre de tours dans `claude_code` ; limite de messages de l'échantillon à défaut [Fragile] |
| déclenchement | scoreur qui cherche un `ToolEvent` `Skill` portant le nom du skill |
| invocation forcée en qualité | entrée préfixée par `/<nom>`, contrôlée par l'`InfoEvent` `skill_command` |
| vérifications de qualité | scoreur à 1 si toutes passent, juge `judge_model` en dernier recours |
| `judge_calibration` | tâche du juge sur les réponses notées par une personne, qui produit les paires |
| réducteurs | aucun pour décider ; `pass_at_k` et `pass_k` gardés dans les journaux pour lecture |

## 5. Plan de tests

Les tests du domaine passent sans agent ni réseau. Ils recalculent chaque chiffre de
`skill-eval-result.example.yaml` à partir de comptes par cas reconstitués : pass^10 = 0,533 =
8/15 impose huit cas de qualité à 10/10, puis pass^9 un cas à 9/10. Hypothesis vérifie les
propriétés : bornes, monotonie en k, stabilité du découpage quand on ajoute des cas, verdict qui
ne recule pas quand le score monte. Le test du rendu compare le résultat produit, rechargé, à
l'exemple chargé. Le test de la CLI va de bout en bout, des fichiers d'exemple au résultat et au
code de sortie 3. Un test d'architecture contrôle les imports. Seuils : 85 % de couverture
globale, 75 % sur les lignes modifiées d'une PR, complexité cognitive de 15 au plus par
fonction (aujourd'hui : 100 % de couverture, complexité de 10 au maximum).

L'exécuteur Inspect se testera d'abord sur des journaux d'évaluation construits à la main, puis
sur un cas témoin réel qui nomme le skill et doit toujours le déclencher.

## 6. Job CI d'évaluation

- **Déclencheurs** : une PR qui modifie `skills/<nom>/**` évalue ce skill ; un passage sur `main`
  évalue tout le jeu et conserve l'enregistrement comme référence.
- **Cas lancés en PR** : les cas réservés seulement, qui décident du verdict, soit 40 % des
  essais ; les cas de réglage tournent sur `main`.
- **Volume par évaluation complète**, sur l'exemple : 1 000 essais d'invocation courts
  (100 cas × 10), 380 essais de qualité (38 × 10), 760 avec l'écart avec et sans skill. En PR :
  400 essais d'invocation et 150 de qualité (300 avec l'écart).
- **Coût** : non estimé. Il faut mesurer les jetons d'un essai d'invocation et d'un essai de
  qualité sur le skill pilote ; le prompt système et les outils de Claude Code pèsent sur chaque
  essai, même court [Sans source fiable].
- **Code de sortie** : 0 diffusable, 1 un seuil échoué, 2 erreur d'usage, 3 indécis, 4 entrée
  invalide ou sortie impossible à écrire, 5 erreur interne (un plantage ne sort jamais avec 1).
  Un pipeline peut laisser passer 3 avec un avertissement et bloquer 1, mais voir l'issue sur
  `minimum_cases`, qui peut transformer un échec net en 3.

## 7. Risques

| Choix | Risque | Meilleur argument contre le choix |
|---|---|---|
| Recalculer estimateurs et intervalles dans le domaine | Divergence avec Inspect | Inspect fournit déjà `pass_k`, `ci` et `ci_wilson` ; la vérification croisée devrait devenir un test sous option |
| Copier les skills hors de `skills=` | Plus de code, contournement d'une API d'Inspect | Inspect pourrait assouplir sa validation et rendre la copie inutile |
| Student par cas | Intervalles trop étroits près de 0 ou 1, verdict inversé dans le cas dégénéré (issue) | `ci_wilson` groupé d'Inspect traite les bords sans rupture |
| Découpage par nom | Nombre de cas réservés aléatoire (issue) | L'exemple suppose un nombre exact de cas réservés |
| Bac à sable Docker en CI | Runner privilégié, surface d'attaque | Kubernetes isole mieux, au prix d'un cluster |
| SciPy pour le quantile de Student | 34 Mo de dépendance pour une fonction | Inspect calcule ce quantile sans dépendance, en une trentaine de lignes |
| Dépôt sur GitHub | Le dossier prévoyait GitLab CI et un rapport de merge request | Si les skills vivent sur GitLab, le job doit y tourner |

## 8. Questions ouvertes

Tranchées par ce cadrage, sauf avis contraire :

- **Stockage de la référence** : l'enregistrement de comptes par cas du dernier passage sur
  `main`, en artefact, et non le fichier de résultat.
- **Cas lancés en PR** : les cas réservés seulement.

À trancher par Hector Basset (une issue chacune) :

- agents de la V1 (proposition : Claude Code seul) ;
- plateforme du job d'évaluation : GitHub Actions ou GitLab CI ;
- taille d'échantillon de Wilson dans le cas dégénéré, et plus largement l'intervalle près des
  bords ;
- découpage par nom ou à effectif exact, et le nombre de cas à conseiller ;
- diagnostics calculés sur les cas réservés alors que le résumé invite à les corriger ;
- juge non fiable : seuils de qualité forcés à « indécis » (implémenté, à confirmer) ;
- `skill_version` calculée sur `SKILL.md` seul ou sur tout le dossier du skill ;
- deux niveaux d'exigence selon le risque du skill, après le pilote ;
- collecte de demandes réelles par hooks et conformité au RGPD ;
- nom définitif de l'outil.
