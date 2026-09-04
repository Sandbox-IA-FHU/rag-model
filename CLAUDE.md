# Consignes Claude Code — rag-model

Complète le `CLAUDE.md` de l'organisation (dépôt `.github`), il ne l'annule
pas. Les conventions d'écriture Python sont dans
[CONVENTIONS-PYTHON.md](CONVENTIONS-PYTHON.md) — à lire avant toute
modification de code.

## Ce qu'est ce dépôt

Un **modèle** de projet RAG. Le code est volontairement minuscule : ce qu'il
transmet, c'est une méthode, pas une bibliothèque. Une modification qui rend le
code plus capable mais moins lisible est une régression.

## Commandes

```bash
uv sync                      # installation
uv run ruff format .         # formatage
uv run ruff check .          # lint
uv run pytest                # tests, sans réseau ni clé
uv run --env-file .env python scripts/ask.py "une question"
uv run --env-file .env python scripts/evaluate.py --limite 3
```

Aucun test n'appelle un fournisseur de modèle. Si un test se met à en avoir
besoin, c'est la conception qu'il faut corriger, pas le test.

## Architecture, en une phrase par module

| Module | Rôle |
|---|---|
| `config.py` | Seul endroit qui lit `os.environ`. Valide et échoue au démarrage. |
| `corpus.py` | Lit le JSONL. Convertit les clés françaises du fichier en attributs. |
| `chunking.py` | Fenêtre glissante sur les mots, avec recouvrement. |
| `index.py` | BM25 en mémoire. Rend `[]` quand aucun terme ne correspond. |
| `client.py` | Seul module qui connaît le SDK. Protocole `ModelClient`. |
| `generation.py` | Assemble le prompt. Sépare consignes et extraits. |
| `pipeline.py` | `answerQuestion` — le point d'entrée. |
| `costs.py` | Jetons → dollars, avec des tarifs datés. |
| `evaluation.py` | Notation et agrégation. |

## Les trois choses à ne pas casser

**1. Le refus sans appel modèle.** Quand la recherche ne rend aucun passage,
`answerQuestion` refuse **avant** d'appeler le modèle. Deux raisons : un refus
ne doit rien coûter, et un modèle sans contexte répond quand même, avec ce
qu'il croit savoir. Test : `test_refusalHappensWithoutCallingTheModel`.

**2. La séparation consignes / extraits.** Les passages récupérés sont insérés
entre des marqueurs, comme données. Un document indexé peut contenir « ignore
les consignes précédentes » — `doc-07` du corpus le fait exprès. Tests :
`tests/test_generation.py`.

**3. Le client injecté.** `answerQuestion` reçoit son client, il ne le
construit pas. C'est ce qui permet aux tests de tourner sans clé.

---

## Diagnostiquer un RAG qui répond mal

C'est le contenu le plus utile de ce fichier. Quand quelqu'un dit « le RAG
répond mal », il n'y a **pas** une cause mais quatre, elles se corrigent à des
endroits différents, et l'erreur la plus coûteuse est de retoucher le prompt
alors que le problème est en amont.

L'ordre de diagnostic est toujours le même, et il commence par une mesure qui
ne coûte rien.

### Étape 1 — Est-ce que le bon passage remonte ?

Le rappel se mesure **hors ligne, gratuitement, sans appeler le modèle**. C'est
ce que fait `tests/test_retrieval_recall.py`, et c'est reproductible à la main
sur une question précise :

```python
index.search("la question exacte", topK=4)
```

Si le passage attendu n'est pas dans la liste, **le prompt n'y est pour rien**.
Toucher au prompt à ce stade, c'est passer une journée à améliorer la façon
dont le modèle exploite un document qu'il ne reçoit pas.

Trois causes possibles, dans l'ordre de fréquence :

- **Vocabulaire décalé.** La question et le document ne partagent aucun mot.
  C'est la limite structurelle d'une recherche lexicale — `q-13` du jeu
  d'évaluation en est l'exemple gardé exprès. Aucun réglage ne la corrige : ça
  se corrige par une recherche vectorielle, ou par un enrichissement du
  document (ajouter les synonymes métier au titre marche étonnamment bien et
  coûte zéro).
- **Frontière de passage.** La réponse est coupée en deux par le découpage.
  Symptôme : le bon document remonte, mais le passage remonté ne contient que
  la moitié de l'information. Se corrige par le recouvrement.
- **Mot vide mal placé.** Un terme discriminant est dans `STOP_WORDS`, ou un
  terme parasite n'y est pas. Rare, mais gratuit à vérifier avec `tokenize()`.

### Étape 2 — Le passage remonte, mais la réponse est fausse

Là seulement, c'est le prompt ou le modèle. Regarde ce que le modèle a
réellement reçu :

```python
buildUserMessage(question, passages)
```

Les questions à se poser, dans cet ordre : le passage contient-il vraiment la
réponse (relis-le, ne suppose pas) ; y a-t-il un passage **contradictoire**
dans les quatre remontés ; le modèle a-t-il complété avec sa connaissance
générale au lieu du document.

Ce troisième cas est le plus dangereux parce que la réponse est juste — jusqu'au
jour où le document dit autre chose que le monde. Il se détecte en posant une
question dont la vraie réponse et la réponse du document diffèrent.

### Étape 3 — Le système refuse alors qu'il ne devrait pas

Deux chemins de refus dans cette chaîne, et ils ne se corrigent pas au même
endroit :

- **Refus par la recherche** (`answer.refused is True`) : aucun passage n'a de
  score positif. C'est l'étape 1, pas le prompt.
- **Refus par le modèle** (`looksLikeRefusal(answer.text)`) : des passages sont
  arrivés, le modèle a jugé qu'ils ne répondaient pas. C'est le prompt, ou les
  passages sont effectivement hors sujet — ce qui ramène à l'étape 1.

Distinguer les deux prend dix secondes et évite de corriger le mauvais.

### Étape 4 — Le système répond alors qu'il devrait refuser

Le mode d'échec le plus grave, et le seul dont le seuil est à 100 %. Un système
qui répond avec assurance à une question dont la réponse n'existe pas dans ses
données est un système dangereux : personne ne vérifie une réponse qui a l'air
sûre d'elle.

Attention au piège : BM25 remonte presque toujours **quelque chose** dès qu'un
seul mot est commun, aussi accessoire soit-il. Trois cas de refus du jeu le
montrent, mesurés le 2026-09-04 :

| Cas | Passage remonté | Seul terme commun |
|---|---|---|
| `q-20` chiffre d'affaires | `doc-01#001` | `ete` (« a **été** identifié ») |
| `q-22` adresse personnelle | `doc-05#000` | `adresse` (« à l'**adresse** du compte ») |
| `q-23` personnes à l'entrepôt | `doc-03#000` | `entrepot` (« repart vers l'**entrepôt** ») |

Le refus repose donc sur le **prompt**, pas sur la recherche : celle-ci a
fourni un passage, simplement hors sujet. C'est voulu, et c'est ce que ces
trois cas mesurent.

`q-20` illustre au passage un vrai défaut, gardé exprès : `ete` est une forme
conjuguée de « être » absente de `STOP_WORDS`. L'ajouter est une correction
légitime — et un bon exercice, parce qu'elle **déplace** le cas d'un chemin de
refus à l'autre : `q-20` ne remonterait plus rien et refuserait gratuitement,
sans appel modèle. Le score global ne bougerait pas, la facture si. C'est
exactement le genre d'effet qu'on ne voit pas sans mesurer les deux chemins
séparément.

---

## Les paramètres qu'on est tenté de bouger

Quatre, et ils ne coûtent pas la même chose. Un seul à la fois, avec un run
avant et un run après — deux changements simultanés produisent un résultat
qu'on ne peut attribuer à rien.

| Paramètre | Effet réel | Coût |
|---|---|---|
| `TOP_K` (`pipeline.py`) | Monter le rappel. Le levier le plus efficace, et le plus cher. | Le contexte croît **linéairement** : passer de 4 à 8 double la partie variable du prompt, donc du coût d'entrée. |
| `CHUNK_SIZE_WORDS` | Passages plus longs = plus de contexte autour de la réponse, mais recherche moins précise (un long passage contient tout, donc match tout). | Idem, linéaire. |
| `CHUNK_OVERLAP_WORDS` | Corrige les réponses coupées par une frontière. | Augmente le **nombre** de passages, donc la taille de l'index et le temps de recherche. Pas le coût modèle. |
| `BM25_K1` / `BM25_B` | Presque rien, à ce volume. | Gratuit — et c'est précisément pour ça qu'on est tenté d'y passer du temps. Ne commence pas par là. |

Règle pratique : monter `TOP_K` fait presque toujours monter le rappel, et fait
toujours monter la facture. La question n'est jamais « est-ce que ça
s'améliore » mais « est-ce que ça s'améliore assez pour ce que ça coûte ».

---

## Où part l'argent dans un RAG

La structure de coût d'un RAG n'est pas celle d'un appel simple, et elle
surprend systématiquement :

- **L'entrée domine.** Le prompt contient `TOP_K` passages complets ; la
  réponse fait trois phrases. Un RAG est un système à entrée lourde et sortie
  légère, contrairement à un système de rédaction.
- **Le refus est gratuit** quand il vient de la recherche. C'est un argument de
  conception, pas seulement de sécurité : sur un corpus où beaucoup de
  questions sont hors périmètre, la porte de refus fait baisser la facture.
- **Le coût par question est ce qui se compare**, pas le coût par appel. Deux
  centimes par question sur 300 questions par jour, c'est de l'ordre de deux
  mille euros par an, et ça se compare à ce que coûte la réponse manuelle. Le
  coût par appel ne se compare à rien.

Ne convertis jamais un nombre de mots en nombre de jetons avec un ratio de
tête : le rapport dépend de la langue et du contenu. Le comptage se demande au
fournisseur, ou se lit dans `usage` après un vrai appel. Les tarifs sont dans
`costs.py` avec leur date de relevé ; si tu les mets à jour, mets aussi la date
à jour.

---

## Les pièges propres à ce dépôt

**Le corpus change, les runs passés meurent.** Ajouter ou modifier un document
change l'index, donc le rappel, donc tout. Un run n'est comparable qu'à un run
sur le **même corpus**. Si le corpus bouge, dis-le et propose de refaire un run
de référence — sinon la comparaison suivante sera fausse sans que personne ne
le voie.

**Le prompt se spécialise sur le jeu.** À force de corriger les cas qui
échouent, on finit par écrire un prompt qui traite ces cas-là. Le score monte,
la performance réelle non. C'est pour ça que `questions_reserve.jsonl` existe,
et qu'on n'y regarde **jamais** le détail des erreurs. Un écart de plus de
quelques points entre les deux jeux est le diagnostic.

**La notation par mots-clés se laisse tromper dans les deux sens.** Une bonne
réponse formulée autrement est comptée fausse ; une réponse fausse contenant le
bon mot est comptée juste. Quand un score bouge de peu, va lire les réponses
avant de conclure quoi que ce soit.

**`q-16` (« livré un samedi ») est un cas faible** : son mot-clé attendu est
présent dans la question elle-même. Il est gardé pour la couverture, mais ne
fonde jamais une conclusion dessus.

**Un score de 100 % sur le jeu principal n'est pas une bonne nouvelle.** C'est
le signe que le jeu est trop facile, pas que le système est parfait. Le bon
réflexe est d'ajouter des cas difficiles, pas de célébrer.

---

## Ce qu'on attend d'une session ici

**Avant de coder, cadrer.** Sur une modification qui touche la qualité des
réponses : quelle est la question, et comment saura-t-on que c'est mieux ? La
commande `/cadrer` sert à ça.

**Diagnostiquer avant de corriger.** L'ordre est toujours : rappel d'abord
(gratuit), prompt ensuite (payant). Proposer une modification de prompt sans
avoir vérifié le rappel est l'erreur la plus courante sur ce type de projet.

**Une modification de prompt se mesure.** Un run avant, un run après, un seul
paramètre changé.

**Ne pas conclure sur un écart faible.** Sur 25 cas, 82 % et 85 % ne sont pas
distinguables : c'est un cas de différence. Traduis toujours un écart en nombre
de cas avant de le commenter.

**Ne pas ajouter de dépendance** sans raison écrite. En particulier : pas de
framework d'orchestration, pas de base vectorielle « pour voir ». Le passage à
une recherche vectorielle est une décision qui s'appuie sur un rappel mesuré et
sur un nombre de cas en échec, et elle se justifie dans le README.

**Ne jamais inventer un chiffre.** Prix, limites de contexte, performances : si
la valeur n'est pas vérifiée dans la session, le dire plutôt que l'écrire.

## Ce qui ne va jamais dans le dépôt

Une donnée réelle, un extrait de document client, une clé, un nom de client, un
fichier de trace, un notebook avec ses sorties. `evaluations/jeux/` est la
seule zone où un fichier de données a sa place, et son contenu est inventé.

Attention particulière ici : une **trace de RAG contient les passages
récupérés**, donc le contenu métier des documents, intégralement. C'est la
fuite la plus facile à provoquer sur ce type de projet — un `print` de debug
laissé dans `generation.py` et redirigé vers un fichier suffit.

## Commandes et sous-agents

| | |
|---|---|
| `/cadrer` | Écrire question, mesure et seuil avant de coder |
| `/prompt` | Créer une version de prompt sans écraser la précédente |
| `/evaluer` | Lancer l'évaluation et écrire le fichier de run |
| `/avant-pr` | Passer la checklist de revue sur son propre diff |
| `relecteur-resultats` | La conclusion est-elle soutenue par ses chiffres ? |
| `verificateur-donnees` | Le diff contient-il donnée, clé ou nom de client ? |
