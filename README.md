# rag-model — dépôt modèle pour un projet RAG

> **Statut** : actif
> **Mise à jour** : 2026-09-04
> **Question posée** : quelle structure minimale permet de démarrer un projet de
> question-réponse sur documents dans cette organisation, sans repartir d'une
> page blanche et sans réinventer la mesure ?
> **Verdict** : en service. Modèle repris via « Use this template ».

Ce dépôt est un **modèle**, pas un projet. Il contient une chaîne RAG complète,
minuscule et fonctionnelle, dont l'intérêt n'est pas le code mais la méthode :
où vivent les prompts, comment on mesure, ce qu'on ne commite jamais, et
comment on travaille avec Claude Code dessus.

Le premier commit d'un projet dérivé **remplace cet en-tête par le sien** —
sa question, son statut, sa date. Un dépôt qui garde l'en-tête du modèle ment
sur ce qu'il est.

---

## Démarrer

Prérequis : Python 3.13, [`uv`](https://docs.astral.sh/uv/), Git 2.40+.

```bash
uv sync
uv run ruff check .
uv run pytest
```

Ces trois commandes doivent passer sur un dépôt fraîchement cloné, sans clé
d'API et sans réseau. C'est volontaire : rien de ce qui est testé ici n'appelle
un fournisseur de modèle.

Pour poser une vraie question, il faut une clé :

```bash
cp .env.exemple .env
```

Renseignez `ANTHROPIC_API_KEY` dans `.env`, puis :

```bash
uv run --env-file .env python scripts/ask.py "quelle est la procédure de retour ?"
```

Et pour lancer l'évaluation complète, qui écrit un fichier de run daté :

```bash
uv run --env-file .env python scripts/evaluate.py
```

`.env` est dans `.gitignore`. Il n'y entre jamais.

---

## Ce que fait la chaîne

Cinq étapes, chacune dans son module, chacune testable seule :

```
corpus (jsonl)
  → chunking.py    découpage en passages avec recouvrement
  → index.py       index lexical BM25, en mémoire, sans dépendance
  → retrieval.py   les k passages les plus proches de la question
  → generation.py  un appel modèle, contexte et consignes séparés
  → pipeline.py    assemble le tout, renvoie réponse + sources + coût
```

Deux comportements méritent d'être regardés avant le reste, parce que ce sont
eux qui distinguent un RAG utilisable d'une démonstration :

**Le refus.** Quand aucun passage récupéré ne dépasse le seuil de pertinence,
la chaîne répond « je ne sais pas » **sans appeler le modèle**. Un système qui
répond avec assurance à une question dont la réponse n'est pas dans le corpus
est un système dangereux, et c'est le mode d'échec le plus courant d'un RAG.

**L'injection de prompt.** Les passages récupérés sont insérés dans le prompt
comme **données**, jamais comme consignes. Le corpus d'exemple contient
volontairement un document empoisonné (`doc-07`) qui tente de détourner le
système ; le jeu d'évaluation contient le cas correspondant. Si vous modifiez
`generation.py`, ce test doit rester vert.

---

## Choix techniques, et pourquoi

L'organisation fige Python 3.13, `uv`, `ruff` et `pytest`. Tout le reste se
choisit par projet et se justifie ici. Pour ce modèle :

| Choix | Pourquoi |
|---|---|
| Recherche **lexicale BM25**, écrite à la main (~70 lignes) | Aucune dépendance, aucun serveur, aucune seconde clé d'API, déterministe et testable hors ligne. Sur quelques centaines de documents, l'écart avec une recherche vectorielle ne justifie pas encore le coût d'exploitation. |
| **Pas de base vectorielle** | Voir ci-dessous : c'est une décision à prendre avec des chiffres, pas par défaut. |
| **Pas de framework d'orchestration** | Cette chaîne fait cinq appels de fonction. Un framework ajouterait une abstraction, une dépendance jeune, et masquerait exactement ce que ce modèle est censé montrer. |
| Fournisseur de modèle : **Anthropic** | Un seul appel modèle dans toute la chaîne, isolé dans `generation.py`. En changer se fait à un seul endroit. |

**Quand passer à une recherche vectorielle.** Quand la mesure le dit, pas
avant. Le signal : le rappel plafonne alors que les passages pertinents
existent, et les échecs sont des questions qui n'emploient pas les mots du
document. Mesurez le rappel de la recherche **séparément** de la qualité de la
réponse — `scripts/evaluate.py` le fait déjà : c'est ce découpage qui permet de
savoir laquelle des deux étapes échoue.

Le dépôt en contient un exemple réel, et c'est la raison pour laquelle il est
resté dans le jeu. Le rappel de la recherche sur le jeu principal est de
**18 cas sur 19** (mesuré le 2026-09-04, sans aucun appel modèle — le rappel se
mesure hors ligne et gratuitement). Le cas manquant est `q-13` :

> « J'ai reçu un article **cassé**, est-ce que je paie le renvoi ? »

`doc-01` répond à cette question, mais il écrit « produit **défectueux** ».
Aucun mot commun, donc aucun passage remonté, donc refus. C'est précisément
l'échec qu'une recherche vectorielle corrigerait — et c'est un cas sur 19, ce
qui ne justifie pas encore d'ajouter une base vectorielle. La décision se prend
quand ces cas deviennent nombreux, pas quand on en trouve un.

---

## Le seuil

Écrit avant de mesurer, révisé explicitement quand il change. Celui-ci est un
**exemple à remplacer** par le vôtre au premier commit :

> Rappel de la recherche : au moins 85 % des questions ont leur passage de
> référence dans les 4 premiers résultats. Qualité de réponse : au moins 80 %
> de réponses correctes, et **100 % de refus corrects** sur les questions hors
> corpus. Coût maximum 2 centimes par question. Latence médiane sous 4 s.

Le refus est à 100 % et pas à 80 % délibérément : une réponse inventée coûte
plus cher qu'une absence de réponse.

---

## Arborescence

```
prompts/              un fichier par version, jamais modifié en place
evaluations/
  jeux/               corpus et questions — données INVENTÉES, seule zone du
                      dépôt où un fichier de données a sa place
  runs/               résultats horodatés, un fichier JSON par exécution
src/rag/              la chaîne, un module par étape
tests/                miroir de src/, aucun appel réseau
scripts/              points d'entrée en ligne de commande
.claude/              commandes et sous-agents Claude Code de ce dépôt
CONVENTIONS-PYTHON.md règles d'écriture du Python — à lire avant le 1er commit
```

---

## Travailler avec Claude Code ici

`CLAUDE.md` décrit ce dépôt à Claude. Quatre commandes sont fournies :

| Commande | Ce qu'elle fait |
|---|---|
| `/cadrer` | Écrit la question, la mesure et le seuil **avant** de coder |
| `/prompt` | Crée une nouvelle version de prompt sans écraser la précédente |
| `/evaluer` | Lance l'évaluation, écrit le fichier de run, compare au précédent |
| `/avant-pr` | Passe la checklist de revue sur votre propre diff |

Et deux sous-agents : `relecteur-resultats` (une conclusion est-elle soutenue
par ses chiffres ?) et `verificateur-donnees` (le diff contient-il une donnée,
une clé, un nom de client ?).

---

## Ce que ce modèle ne fait pas

Il ne gère ni les PDF, ni l'OCR, ni le découpage sémantique, ni le reclassement
des passages, ni la conversation multi-tours, ni le cache de prompt. Ce sont
des ajouts légitimes — chacun à faire **quand la mesure montre qu'il manque**,
pas au démarrage.

Il ne contient pas non plus de fichier de run d'exemple : un run est le
résultat d'une exécution réelle. `evaluations/runs/GABARIT.json` documente le
format, avec des valeurs nulles. Un chiffre inventé dans un dépôt modèle finit
recopié dans un vrai projet.
