# Cineblast VFE — Plan de migration PySide6/Qt

Version : v01  
Date : 2026-09-01  
Projet : Cineblast VFE  
État : PLAN VALIDÉ par l’utilisateur  
Prochain lot : LOT 0  

---

## 1. Objectif du projet

Transformer l’application actuelle **Cineblast VFE**, actuellement basée sur Tkinter, en une application moderne sous **PySide6 / Qt**, avec :

- une direction artistique plus aboutie ;
- une meilleure ergonomie ;
- une interface plus adaptée à un usage graphique / cinéma / montage YouTube ;
- une conservation maximale de la logique métier existante ;
- une migration progressive, validée lot par lot.

L’application sert à extraire des images de films pour les réutiliser ensuite dans des montages YouTube.

---

## 2. Décision principale

La migration vers **PySide6/Qt** est validée dans son principe.

Ordre recommandé :

1. Définir une direction artistique cible.
2. Créer un prototype visuel Qt limité aux composants principaux.
3. Migrer progressivement l’application existante vers Qt.
4. Valider chaque lot avant de passer au suivant.

Il ne faut pas faire une migration “big bang”.

---

## 3. Règles de travail

### 3.1. Validation par lot

Chaque lot doit être validé explicitement par l’utilisateur.

Formules de validation :

```text
LOT X VALIDÉ