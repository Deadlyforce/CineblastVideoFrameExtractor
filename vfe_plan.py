"""Plan de capture — logique extraite de App._compute_targets (refactor A1)."""


def compute_targets(duration, fps, mode, count, interval):
    """Retourne la liste des timestamps à extraire.

    Paramètres :
      duration : durée de la vidéo en secondes (float)
      fps      : images/seconde (peut être None/0 → 25 par défaut)
      mode     : "count" ou "interval"
      count    : nombre d'images souhaité (mode "count")
      interval : intervalle en secondes (mode "interval")
    """
    dur = duration
    fps = fps or 25.0
    # v4.11 (E77) : marge de sécurité pour la dernière frame.
    # Un seek exactement à la durée tombe souvent après la dernière image décodable.
    safe = min(0.5, max(0.1, 2.0 / max(fps, 1.0)))
    end = max(0.0, dur - safe)
    if end <= 0.0:
        return [0.0]
    if mode == "count":
        n = max(1, count)
        if n == 1:
            return [0.0]
        return [i * end / (n - 1) for i in range(n)]
    iv = max(1, interval)
    targets = []
    t = 0.0
    while t <= end + 0.001:
        targets.append(min(t, end))
        t += iv
    return targets