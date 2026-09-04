---
description: Lancer l'évaluation, écrire le run, comparer au précédent
---

Lance l'évaluation et interprète le résultat. Ne conclus rien avant d'avoir les
chiffres sous les yeux.

Étiquette du run (ou vide) : $ARGUMENTS

## Marche à suivre

1. **Avertis du coût avant de lancer.** Dis combien de cas contient le jeu,
   donc combien d'appels modèle au maximum, et avec quel modèle. Propose
   `--limite 3` d'abord si rien n'a tourné depuis longtemps.
2. Lance :
   `uv run --env-file .env python scripts/evaluate.py --etiquette <étiquette>`
3. Lis le fichier de run produit dans `evaluations/runs/`.
4. Trouve le run comparable le plus récent — **même jeu, même modèle**. S'il
   n'y en a pas de comparable, dis-le et ne compare pas.

## Ce que tu rends

Un compte rendu court, en français :

- Les trois taux : rappel de recherche, réponse correcte, refus correct — **et
  le découpage par type de cas**. Un 90 % global avec tous les échecs sur les
  refus décrit un système inutilisable affiché comme un succès.
- Le coût total et le coût par question, en dollars, avec la date de relevé des
  tarifs.
- La latence médiane et le p95.
- L'écart avec le run précédent, **et s'il est interprétable**. Sur 25 cas, un
  écart de moins de 10 points n'est probablement pas significatif : dis-le
  plutôt que d'annoncer une amélioration.
- Quels cas ont échoué, et si les échecs sont concentrés sur un type. Un score
  seul dit qu'il reste des erreurs ; il ne dit pas si elles sont regroupées sur
  un type de cas qu'on pourrait sortir du périmètre.

## Pour finir

Propose une phrase pour le champ `commentaire` du fichier de run — c'est le
champ qu'on relit dans six mois — et rappelle de le remplir avant de commiter.

Si le run est meilleur que le précédent, propose de vérifier sur le jeu de
réserve :

```bash
uv run --env-file .env python scripts/evaluate.py --jeu evaluations/jeux/questions_reserve.jsonl --etiquette reserve
```

Un écart de plus de quelques points entre le jeu principal et la réserve
signifie que le prompt s'est spécialisé sur les cas qu'on regardait.
