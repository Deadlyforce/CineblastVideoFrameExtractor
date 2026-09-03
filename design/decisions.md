# Décisions — Cineblast VFE

Format :
Date | Lot | Décision | État | Commentaire

- 2026-09-01 | PLAN | Migration vers PySide6/Qt | VALIDÉ | Plan général validé.
- 2026-09-01 | PLAN | Direction artistique avant migration lourde | VALIDÉ | DA d’abord, puis prototype Qt, puis migration progressive.
- 2026-09-01 | PLAN | Conservation maximale du backend Python | VALIDÉ | vfe_config, vfe_ffmpeg, vfe_plan, vfe_utils, vfe_workers à préserver.
- 2026-09-01 | LOT 1B | Zoning validé avec ajustement Zone D | VALIDÉ | Zone D : pas d’actions rapides Marquer / Supprimer / Déplacer ; conserver uniquement “Ouvrir dans le dossier”.
- 2026-09-01 | LOT 1C-A | Palette darkroom ambre v01 | VALIDÉ | Palette proposée validée.
- 2026-09-01 | LOT 1C-B | Typographie validée | VALIDÉ | Segoe UI + Consolas, tailles et graisses validées, titres de sections en minuscules 12 px.
- 2026-09-01 | LOT 1C-C | Espacements, radius, bordures | VALIDÉ | Valeurs proposées validées.
- 2026-09-01 | LOT 1C | Tokens visuels | VALIDÉ | Palette, typographie et espacements validés.
- 2026-09-02 | LOT 1D | Mockup écran principal | VALIDÉ | Mockup conforme à la DA ; observations reportées au backlog.
- 2026-09-02 | LOT 1 | Direction artistique cible | VALIDÉ | LOT 1 terminé (1A, 1B, 1C, 1D).
- 2026-09-02 | LOT 2A | Sandbox composants PySide6 | VALIDÉ | Thème darkroom ambre rendu correctement dans Qt : boutons, slider, switches, segmented, badges, carte, combo.
- 2026-09-02 | LOT 2B | Position de la barre de statut | VALIDÉ BAS | Le mockup la montrait en haut ; décision finale : Zone E en bas, comme dans le zoning LOT 1B.
- 2026-09-02 | LOT 2B | Panneau gauche | AJUSTEMENTS | Pas de scrollbar horizontale ; boutons de chemin avec ellipse (…) au lieu de texte coupé ; carte Plan sous le slider et au-dessus du switch frames noires ; badges FFMPEG / HDR10 PQ de largeur identique ; fenêtre plus haute au démarrage.
- 2026-09-02 | LOT 2B | Comportement de la grille | VALIDÉ RÉGLAGES | Les combos Colonnes / Vignettes gouvernent : la zone centrale et la fenêtre s’adaptent à ces choix ; le redimensionnement manuel peut casser l’affichage, c’est accepté ; un nouveau choix rétablit l’interface.
- 2026-09-02 | LOT 2B | Sélecteur de taille d’aperçu | VALIDÉ | Présent en Zone D ; valeurs 200 à 700 px par pas de 50 ; gouverne la largeur de la colonne droite (formule preview + 52, identique à l’app actuelle). La valeur réelle sera relue depuis VFE_Config.json dans la future app (LOT 7+).
- 2026-09-02 | LOT 2B | Hauteurs des badges | VALIDÉ | Badges FFMPEG / HDR10 PQ (Zone A) et badges compteurs (Zone B) : hauteur fixe 28 px, cohérente avec les petits boutons.
- 2026-09-02 | LOT 2B | Sélecteur de tone mapping | VALIDÉ | Options Hable / Mobius / Reinhard en Zone A, visibles uniquement en mode HDR ; Hable par défaut. Dans la future app, affichage conditionné par la détection HDR (LOT 4+).
- 2026-09-02 | LOT 2 | Prototype visuel PySide6 | VALIDÉ | Sandbox composants (2A) + écran factice (2B v07) validés. Thème darkroom ambre confirmé dans Qt.
- 2026-09-02 | LOT 3 | Shell principal Qt | VALIDÉ | Structure 3 fichiers (theme/widgets/main), config lue en lecture seule, gouverne des réglages OK. confirm_delete reste false (choix utilisateur).
- 2026-09-02 | LOT 4 | Troncature de l’aperçu | VALIDÉ | Quand l’écran plafonne et que l’aperçu est rogné : avertissement orange sous l’aperçu indiquant les px perdus à gauche et à droite.
- 2026-09-02 | LOT 5 | Extraction Qt | VALIDÉ | Pool ffmpeg 3 workers, flush ordonné, progression + ETA, annulation, ré-extraction, journal [Qt] ; config toujours lecture seule.
- 2026-09-02 | LOT 5 | Bug chemin vidéo | CORRIGÉ | L’extraction utilisait cfg["video_path"] (lecture seule) au lieu de la vidéo courante ; ajout de self._video_path, purge des échecs au changement de vidéo, garde anti-analyse-HDR-périmée.
- 2026-09-02 | LOT 5 | Extraction Qt | VALIDÉ | Pool 3 workers, flush ordonné, annulation, ré-extraction des échecs, journal [Qt]. Config toujours lecture seule.
- 2026-09-03 | LOT 6 | Grille réelle Qt | VALIDÉ | Vignettes virtualisées (fluides à 500 images), sélection clic/Ctrl/Shift/rectangle, flèches, hover, marquage session, badges vivants, Rafraîchir, gouverne OK.
- 2026-09-03 | LOT 7 | Flèches globales | FIX | Filtre d’événements applicatif : les flèches pilotent la grille quel que soit le focus (sauf champ / combo / liste).
- 2026-09-03 | LOT 8 | Switch confirmation | FIX | Le switch pilote confirm_delete en mémoire (fichier inchangé jusqu’au LOT 10).
- 2026-09-03 | LOT 8 | Marquage / suppression / déplacement | VALIDÉ | Corbeille (send2trash + fallback), confirmation pilotée par le switch en mémoire, vider avec confirmation systématique, déplacement numéroté continu vers dossier de travail, états de boutons contextuels.
- 2026-09-03 | LOT 9A | Raccourcis + états vides + tooltips | VALIDÉ | Ctrl+A / Échap globaux, états vides contextuels, tooltips utiles. (Toasts, dialogue de préférences et détails repliables → backlog, non repris de l’ancienne app.)
- 2026-09-03 | LOT 9 | Finitions | VALIDÉ | 9A : Ctrl+A / Échap, états vides, tooltips. 9B : focus visible, hover segmented, titre “Cineblast VFE”.
- 2026-09-03 | LOT 10A | Correctifs UX | VALIDÉ | Import ACCENT_BORDER (fin des erreurs painter) ; rectangle de sélection ~35 % d’opacité ; badges “0 sélectionnée(s)” / “0 marquée(s)” toujours visibles ; dernier aperçu persisté (clé last_preview_file ajoutée au schéma, rétro-compatible).
- 2026-09-03 | LOT 10A | Persistance | VALIDÉ | Auto-save debouncé, bouton Sauvegarder, sauvegarde à la fermeture, marquage + dernier aperçu + hauteur de fenêtre persistés, garde-fou ffmpeg absent.
- 2026-09-03 | LOT 10B | Correctifs | EN COURS | Aperçu redessiné après gouverne (timer 0) ; vignettes live pendant l’extraction ; frames noires : statut court + bouton “Afficher les frames noires (N)” + panneau timecodes sélectionnables ; segmented : texte grisé éteint + pleine largeur ; libellé “Tone mapping”.
- 2026-09-04 | LOT 10B | Panneau frames noires | EN COURS | Vignettes 150 px cliquables ; lightbox 650 px (×, clic hors image, Échap) ; frames noires conservées dans %TEMP%\vfe_black_frames (purgé à chaque extraction), rien dans le dossier d’extraction.
- 2026-09-04 | LOT 10B | Visionneuse frames noires | EN COURS | Fond opaque + carte grise style aperçu ; en-tête “Frame noire — tc” + × visible ; image 800 px centrée.
- 2026-09-04 | LOT 10B | Tests réels | VALIDÉ | Gouverne, extractions SDR/HDR, vignettes live, frames noires (panneau + visionneuse 800 px encadrée), sélection, marquage, suppression, déplacement, persistance : OK.
- 2026-09-04 | LOT 10C | Bascule | VALIDÉ | Lanceurs .bat, icône générée, LISEZMOI_Qt.md, ancienne app archivée (lançable depuis archive_tkinter), racine nettoyée. Migration Tkinter → Qt terminée.