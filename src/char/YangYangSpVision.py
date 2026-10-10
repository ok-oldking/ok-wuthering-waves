"""Yangyang-specific HUD observations. No input or timing decisions here."""

from dataclasses import dataclass, field

import cv2
import numpy as np

from ok.feature.FeatureSet import adjust_coordinates


def white_icon(image):
    """Keep bright neutral glyphs, excluding the pink glow and dimmed icons."""
    bgr = image[:, :, :3]
    low = bgr.min(axis=2)
    high = bgr.max(axis=2)
    return np.where((low >= 200) & ((high.astype(np.int16) - low) <= 65), 255, 0).astype(np.uint8)


@dataclass(frozen=True)
class YangYangSpState:
    attack: str = 'unknown'
    heavy_ready: bool = False
    enhanced_e: str = ''
    liberation_ready: bool = False
    scores: dict = field(default_factory=dict)

    @property
    def followup(self):
        return self.attack in ('air', 'followup')

    @property
    def normal(self):
        return self.attack in ('sword', 'feather') and not self.heavy_ready

    @property
    def signature(self):
        return self.attack, self.heavy_ready, self.enhanced_e, self.liberation_ready


class YangYangSpVision:
    ICON_THRESHOLD = 0.72
    ATTACK_LABELS = {
        'sword': 'yangyang_sp_attack_sword',
        'feather': 'yangyang_sp_attack_feather',
        'azure': 'yangyang_sp_heavy_azure',
        'air': 'yangyang_sp_heavy_air',
        'followup': 'yangyang_sp_heavy_followup',
    }
    E_LABELS = {'crescent': 'yangyang_sp_e_crescent', 'feather': 'yangyang_sp_e_feather'}

    @staticmethod
    def pink_ring(frame, center_x):
        # Use the same bottom/right anchoring as the annotated templates.
        height, width = frame.shape[:2]
        x, y, w, h, _ = adjust_coordinates(center_x - 86, 1934 - 86, 172, 172,
                                            width, height, 3840, 2159)
        roi = frame[y:y + h, x:x + w, :3]
        if roi.shape[:2] != (h, w) or not roi.size:
            return 0.0
        b, g, r = cv2.split(roi.astype(np.int16))
        pink = (r > 145) & (b > 100) & (r - g > 55) & (b - g > 25)
        # Count occupied angular sectors, not overall brightness. A partial
        # liberation energy arc is not a ready ring.
        yy, xx = np.mgrid[:h, :w]
        dx, dy = (xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)
        radius = np.sqrt(dx * dx + dy * dy)
        annulus = (radius >= 0.76) & (radius <= 1.0)
        sectors = ((np.arctan2(dy, dx) + np.pi) * 24 / (2 * np.pi)).astype(int) % 24
        occupied = [np.count_nonzero(pink & annulus & (sectors == i)) >= max(2, w * h / 6000)
                    for i in range(24)]
        return float(sum(occupied) / 24)

    def observe(self, frame, find_one):
        scores = {}

        def score(label):
            box = find_one(label, frame=frame, threshold=0.01,
                           horizontal_variance=0.002, vertical_variance=0.002,
                           frame_processor=white_icon)
            value = float(box.confidence) if box else 0.0
            scores[label] = round(value, 3)
            return value

        attacks = {name: score(label) for name, label in self.ATTACK_LABELS.items()}
        attack = max(attacks, key=attacks.get)
        if attacks[attack] < self.ICON_THRESHOLD:
            attack = 'unknown'
        e_scores = {name: score(label) for name, label in self.E_LABELS.items()}
        enhanced_e = max(e_scores, key=e_scores.get)
        left_ring = self.pink_ring(frame, 2862)
        e_ring = self.pink_ring(frame, 3246)
        r_ring = self.pink_ring(frame, 3630)
        if e_scores[enhanced_e] < self.ICON_THRESHOLD or e_ring < 0.75:
            enhanced_e = ''
        liberation = score('yangyang_sp_liberation') >= self.ICON_THRESHOLD and r_ring >= 0.85
        scores.update(left_ring=round(left_ring, 3), e_ring=round(e_ring, 3), r_ring=round(r_ring, 3))
        heavy_ready = attack in ('feather', 'azure') and left_ring >= 0.75
        return YangYangSpState(attack, heavy_ready, enhanced_e, liberation, scores)
