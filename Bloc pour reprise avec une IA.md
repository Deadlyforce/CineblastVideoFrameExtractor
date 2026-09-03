# CINEBLAST VFE — BLOC DE CONTEXTE (handoff IA → IA)

## 1. PROJET & ÉTAT
- Outil d’extraction de frames vidéo (ffmpeg) pour un utilisateur graphiste (Windows, francophone).
- Migration Tkinter → PySide6 menée par lots, tous validés par l’utilisateur.
- ÉTAT : LOT 0 → 10B VALIDÉS. LOT 10C (icône, lanceurs .bat, LISEZMOI_Qt.md, archivage ancienne app, bascule) DONNÉ MAIS NON EXÉCUTÉ → reprendre là. Ensuite : backlog ou nouvelles demandes.
- POURQUOI : ancienne UI Tkinter datée, dense, emojis, illisible ; objectif = UI pro moderne à fonctionnalités 100 % conservées. Config laissée en lecture seule pendant toute la migration pour protéger l’app de production ; écriture réactivée au LOT 10A.

## 2. PROTOCOLE DE COMMUNICATION (à respecter strictement)
- Français. Un seul lot à la fois. Jamais de foule de modifications.
- Instructions = blocs exacts « Cherche exactement : … / Remplace par : … » (ancres uniques, zéro ambiguïté ; l’utilisateur n’est pas développeur).
- Validation par mots-clés : « LOT X VALIDÉ » / « LOT X NON VALIDÉ : … ».
- Tout changement de design notable = validé AVANT codage ; petits jugements design délégués bienvenus quand l’utilisateur le demande explicitement.
- Erreurs : l’utilisateur colle tracebacks / VFE_Log.txt (faulthandler actif dans main.py).
- Journal des décisions : design/decisions.md ; hors périmètre : design/backlog.md.

## 3. FICHIERS (l’utilisateur les attache)
- Racine, backend PARTAGÉ, ne JAMAIS modifier sans besoin validé : vfe_config.py (schéma dataclass ; clé last_preview_file ajoutée par la Qt), vfe_ffmpeg.py (build_ffmpeg_cmd*, run_ffmpeg, tmp_ok, detect_hdr, zscale_available, get_display_size), vfe_plan.py (compute_targets), vfe_utils.py (hms, tc_str, frame_filename, _parse_tc_from_filename, is_black_frame, dir_parent_label), vfe_workers.py (fallback OpenCV NON porté, backlog), VFE_Config.json, VFE_Log.txt (lignes [Qt]).
- Ancienne app encore à la racine jusqu’au 10C : Video Frame Extractor.py, vfe_widgets.py, vfe_grid.py.
- vfe_qt/ : main.py (MainWindow, toute la logique), theme.py (tokens + QSS, source unique du style), widgets.py (Switch, PathButton, sect, sep, align_badge_widths), grid_qt.py (ThumbCanvas : grille virtualisée, sélection, rubber band). 10C à créer : make_icon.py, app_icon.png.
- design/ : ambiance_v01.md, zoning_v01.md, tokens (palette/typo/espacements), mockups, decisions.md, backlog.md.

## 4. DESIGN SYSTEM (validé, ne pas refaire)
- Ambiance « darkroom cinéma » sombre chaude ; PAS d’emojis, pas de noir pur, pas de glassmorphism, pas de style gamer.
- Couleurs : bg #181512 ; panel #1E1A16 ; card #242019 ; elev #2A241D ; input #322A22 ; borders #3B332A / #4C4135 ; textes #EFE7DB / #C0B3A2 / #8D8070 / #6E6357 ; accent #E0975A (hover #ECAB6E, pressed #C97F42, subtle #3B2A1B, border #A6683B, text #F2B277) ; on_accent #241407 ; success #9CB883 ; warning #D6B25A ; danger #C86455.
- Typo : Segoe UI + Consolas (timecodes/valeurs) ; 11/12/13/15/18 px ; graisses 400/500/600 ; titres de sections minuscules 12 px.
- Radius 4/6/8/10 (base 6) ; espacements 4/8/12/16/24/32 ; hauteurs : petit 28, contrôle 32, primaire 36, Zone B 44, statut 28 ; badges 28 ; grille gap 12 / padding 16 ; sélection bordure 2 px accent ; rubber band accent alpha 90/255.
- Zoning : A gauche 340 px (réglages) ; B barre 44 px ; C grille ; D droite (aperçu + UNIQUEMENT « Ouvrir dans le dossier ») ; E statut en BAS.

## 5. GOUVERNE (règle critique)
- Les réglages gouvernent l’UI : cols+tsize → largeur grille & fenêtre (content_w = cols*t + (cols-1)*12 + 32) ; psize → colonne droite = psize+52.
- Fenêtre = min(idéal, écran) ; setMinimumWidth(400) ; resize en deux temps via QTimer.singleShot(0).
- Plafond écran → colonne droite compressée à droite + avertissement orange « Aperçu tronqué : X px perdus à gauche · Y px perdus à droite ».
- Hauteur du canvas via sizeHint/minimumSizeHint + updateGeometry (JAMAIS resize() dans resizeEvent → stack overflow passé).

## 6. COMPORTEMENTS CLÉS (parité acquise)
- Extraction : pool 3 workers, flush ordonné 0..n, cascade HDR→SDR + tonemap hable/mobius/reinhard (sélecteur visible ssi HDR), filtre noir (seuil /255), annulation, ré-extraction des échecs (traitement immédiat, pas ordonné), vignettes live pendant extraction, ETA.
- Frames noires : conservées dans %TEMP%\vfe_black_frames (purgé à chaque extraction) ; panneau vignettes 150 px ; lightbox 800 px (carte grise style aperçu, ×, clic hors image, Échap).
- Grille : virtualisée (cellules visibles seulement) ; clic / Ctrl / Shift / rectangle ; flèches, Ctrl+A, Échap, Suppr/Retour arrière via eventFilter applicatif (excepté QLineEdit/QComboBox/QAbstractItemView) ; hover ; marquage touche configurable (défaut S).
- Fichiers : corbeille send2trash (+ fallback os.remove) ; « Vider » confirmation toujours ; confirmation suppression = switch en mémoire ; déplacement → workdir numérotation continue generic_%04d.jpg.
- Persistance : auto-save debouncé 400 ms + bouton + closeEvent ; marked_files, last_preview_file, window_h, last_* ; schéma compatible ancienne app.
- Aperçu : re-rendu différé (QTimer 0) après gouverne ; cache 8 pixmaps.

## 7. PIÈGES RÉCURRENTS (leçons)
- QSS : un sélecteur #id bat :hover/:focus → toujours définir #id:hover et #id:focus.
- QScrollArea consomme les flèches → raccourcis globaux via eventFilter QApplication.
- Classes module-level : imports explicites placés AVANT (NameError QLabel passé).
- Signaux émis depuis threads ThreadPoolExecutor = OK (queued).

## 8. BACKLOG (non porté volontairement)
Fallback OpenCV sans ffmpeg (message clair à la place) ; combo « Taille de la fenêtre / Appliquer » ; toasts animés ; dialogue de préférences ; détails repliables ; icônes SVG métier ; pas de 5 s slider intervalle ; libellé « 0 sélectionnées ».

## 9. REPRENDRE LE TRAVAIL
1. Exécuter/valider LOT 10C (instructions déjà fournies : make_icon.py + setWindowIcon, 2 .bat, LISEZMOI_Qt.md, archive_tkinter/ + archive_prototypes/, suppression UI Tkinter de la racine) → « LOT 10C VALIDÉ — BASCULE TERMINÉE ».
2. Ensuite backlog ou nouvelles demandes, même protocole (lots, ancres exactes, validations).
3. Répartition : style → theme.py ; grille → grid_qt.py ; logique → main.py ; backend → untouched sans demande explicite.