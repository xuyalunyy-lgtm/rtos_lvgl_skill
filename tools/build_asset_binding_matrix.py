"""Create the reviewable asset-to-design binding matrix for the multi-page UI.

The matrix is deliberately conservative: an asset is either visually located,
available for a named reuse pattern, or explicitly unbound.  It never assigns
a role from a filename or from the source dimensions alone.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "ui" / "multipage"
ASSET_ROOT = PACKAGE / "assets"
DESIGN_ROOT = PACKAGE / "designs"

HOME_SCENES = [
    "home_default", "home_menu_favorited", "home_menu_guide_favorited",
    "home_menu_guide_unfavorited", "home_menu_unfavorited",
]
PUSH_SCENES = [
    "home_affirmation_favorited", "home_today_affirmation",
    "push_affirmation_favorited", "push_affirmation_unfavorited",
    "push_interactive_favorited", "push_interactive_unfavorited",
    "push_reminder_feedback_favorited", "push_reminder_unfavorited",
    "push_video_favorited", "push_video_unfavorited",
]
STATUS_SCENES = [
    "status_data_loading", "status_data_synced", "status_data_syncing",
    "status_device_initial", "status_device_initial_loading",
    "status_firmware_failed", "status_firmware_updating", "status_hotspot_timeout",
    "status_network_setup_failed", "status_reset_complete", "status_resetting",
    "status_wifi_connected",
]
SCENE_WITH_PET = HOME_SCENES + PUSH_SCENES + [
    "status_data_loading", "status_data_synced", "status_data_syncing",
    "status_firmware_failed", "status_firmware_updating", "status_hotspot_timeout",
    "status_network_setup_failed", "status_resetting", "status_wifi_connected",
]
SCENE_WITH_STATUS_BAR = HOME_SCENES + PUSH_SCENES + STATUS_SCENES


def _binding(
    pages: list[str], layer: str, bbox: list[int] | None, *,
    scale: float | None = 1.0, confidence: str = "visual_confirmed", notes: str = "",
) -> dict[str, Any]:
    item: dict[str, Any] = {"page_ids": pages, "layer": layer, "confidence": confidence}
    if bbox is not None:
        item["bbox"] = bbox
    if scale is not None:
        item["scale"] = scale
    if notes:
        item["notes"] = notes
    return item


# Bboxes are source-canvas coordinates at 480x800.  Entries marked
# visual_approx are retained for the later SSIM refinement loop, but are not
# eligible for automatic UI Spec emission.
CURATED: dict[str, dict[str, Any]] = {
    "backgrounds/background_home.png": {
        "role": "scene_base", "status": "visual_confirmed", "reuse_scope": "home_and_status_scene",
        "bindings": [_binding(HOME_SCENES + STATUS_SCENES, "background", [0, 0, 480, 800])],
    },
    "backgrounds/background_home_source.jpg": {
        "role": "authoring_reference", "status": "reference_only", "reuse_scope": "none", "bindings": [],
        "notes": "Visual duplicate/source counterpart of background_home.png; exclude from runtime pack to avoid duplicate flash cost.",
    },
    "backgrounds/background_affirmation_favorited.png": {
        "role": "scene_base", "status": "visual_confirmed", "reuse_scope": "affirmation_and_push_scene",
        "bindings": [_binding(PUSH_SCENES, "background", [0, 0, 480, 800], confidence="user_confirmed")],
    },
    "backgrounds/background_player.png": {
        "role": "video_thumbnail", "status": "visual_confirmed", "reuse_scope": "push_video_card",
        "bindings": [_binding(["push_video_favorited", "push_video_unfavorited"], "video_thumbnail", [77, 509, 105, 105])],
    },
    "characters/character_pet_idle.png": {
        "role": "foreground_character", "status": "visual_confirmed", "reuse_scope": "scene_character",
        "bindings": [_binding(SCENE_WITH_PET, "character", [96, 124, 305, 428], confidence="user_confirmed", notes="Full source canvas is retained at 305x428; x/y are the visually localized Home anchor.")],
    },
    "characters/character_loading_spirit.png": {
        "role": "foreground_character", "status": "visual_confirmed", "reuse_scope": "device_initial_and_reset_complete",
        "bindings": [_binding(["status_device_initial", "status_device_initial_loading", "status_reset_complete"], "character", [145, 227, 189, 284], confidence="visual_confirmed", notes="Alpha-composite match against the clean Home background; all three designs resolve to the same full source-canvas position.")],
    },
    "content/content_daily_recommendation_01.png": {
        "role": "schedule_carousel_card", "status": "visual_confirmed", "reuse_scope": "schedule_carousel",
        "bindings": [_binding(["home_schedule"], "carousel_previous", [-448, 235, 464, 564], scale=1.0, confidence="user_confirmed_semantics", notes="User confirmed left-to-right order 01 -> 02 -> 03. Retain the complete 464x564 source canvas; it is intentionally positioned partly off-screen.")],
    },
    "content/content_daily_recommendation_02.png": {
        "role": "schedule_carousel_card", "status": "visual_confirmed", "reuse_scope": "schedule_carousel",
        "bindings": [_binding(["home_schedule"], "carousel_current", [8, 235, 464, 564], scale=1.0, confidence="user_confirmed_semantics", notes="Use the complete 464x564 source canvas at native size; do not crop or scale the supplied cut.")],
    },
    "content/content_daily_recommendation_03.png": {
        "role": "schedule_carousel_card", "status": "visual_confirmed", "reuse_scope": "schedule_carousel",
        "bindings": [_binding(["home_schedule"], "carousel_next", [464, 235, 464, 564], scale=1.0, confidence="user_confirmed_semantics", notes="User confirmed left-to-right order 01 -> 02 -> 03. Retain the complete 464x564 source canvas; it is intentionally positioned partly off-screen.")],
    },
    "content/content_player.png": {
        "role": "play_control", "status": "code_drawn", "reuse_scope": "interactive_player_control", "bindings": [],
        "notes": "User confirmed this 136px dark play control must be drawn from primitives rather than bound as a bitmap. Do not add it to the LVGL C asset pack.",
    },
    "content/content_player_page.png": {
        "role": "video_play_overlay", "status": "visual_confirmed", "reuse_scope": "push_video_card",
        "bindings": [_binding(["push_video_favorited", "push_video_unfavorited"], "video_play_overlay", [105, 537, 49, 49], confidence="user_confirmed")],
    },
    "content/content_text_card.png": {
        "role": "resizable_glass_message_card", "status": "visual_confirmed", "reuse_scope": "message_card",
        "bindings": [
            _binding(["home_default", "status_device_initial"], "card_background", [40, 544, 400, 187], notes="Use as an image layer; do not redraw it as a flat LVGL container."),
            _binding(["push_interactive_favorited", "push_interactive_unfavorited"], "card_background", [40, 543, 400, 187], confidence="user_confirmed", notes="Use the complete source canvas as an image layer; the Push text and controls overlay it."),
        ],
        "sizing_policy": "page_specific_bbox_required",
        "notes": "User confirmed Status cards reuse this texture with page-specific dimensions; do not assume a fixed 400x187 bbox outside confirmed pages.",
    },
    "content/content_text_label.png": {
        "role": "schedule_decorative_label", "status": "visual_confirmed", "reuse_scope": "schedule_heading",
        "bindings": [_binding(["home_schedule"], "heading_decoration", [74, 136, 14, 18]), _binding(["home_schedule"], "heading_decoration", [393, 136, 14, 18])],
    },
    "controls/control_back.png": {
        "role": "navigation_icon", "status": "visual_confirmed", "reuse_scope": "plain_page_top_bar",
        "bindings": [_binding(["home_affirmation_empty", "home_schedule"], "system_bar", [18, 9, 48, 48])],
    },
    "controls/control_battery.png": {
        "role": "system_status_icon", "status": "visual_confirmed", "reuse_scope": "system_bar",
        "bindings": [_binding(SCENE_WITH_STATUS_BAR + ["home_affirmation_empty", "home_schedule"], "system_bar", [408, 8, 48, 48])],
    },
    "controls/control_bluetooth.png": {
        "role": "system_status_icon", "status": "visual_confirmed", "reuse_scope": "system_bar",
        "bindings": [_binding(SCENE_WITH_STATUS_BAR, "system_bar", [348, 8, 48, 48])],
    },
    "controls/control_bluetooth_off.png": {
        "role": "system_status_icon", "status": "unbound", "reuse_scope": "none", "bindings": [],
        "notes": "A disconnected Bluetooth visual is supplied but is not reliably distinguishable in the current design exports.",
    },
    "controls/control_dislike.png": {
        "role": "reaction_icon", "status": "unbound", "reuse_scope": "none", "bindings": [],
        "notes": "Do not conflate with the brown control_thumb_down.png used by the affirmation action row.",
    },
    "controls/control_favorite.png": {
        "role": "reaction_icon", "status": "unbound", "reuse_scope": "none", "bindings": [],
        "notes": "Red-heart variant requires a state-level visual distinction from control_primary.png before binding.",
    },
    "controls/control_like.png": {
        "role": "reaction_icon", "status": "unbound", "reuse_scope": "none", "bindings": [],
        "notes": "Gold thumb-up variant is not substituted for control_thumb_up.png without a confirmed state binding.",
    },
    "controls/control_long_press_heart.png": {
        "role": "gesture_feedback", "status": "unbound", "reuse_scope": "none", "bindings": [],
        "notes": "Likely transient long-press feedback; no static screenshot placement is asserted.",
    },
    "controls/control_primary.png": {
        "role": "affirmation_favorite_action", "status": "visual_confirmed", "reuse_scope": "affirmation_action_row",
        "bindings": [_binding(["home_today_affirmation"], "action_icon", [73, 662, 42, 42], confidence="user_confirmed_semantics", notes="User confirmed favorite action semantics.")],
    },
    "controls/control_thumb_down.png": {
        "role": "affirmation_reaction", "status": "visual_confirmed", "reuse_scope": "affirmation_action_row",
        "bindings": [_binding(["home_today_affirmation"], "action_icon", [362, 662, 42, 42], confidence="user_confirmed_semantics", notes="User confirmed dislike action semantics.")],
    },
    "controls/control_thumb_up.png": {
        "role": "affirmation_reaction", "status": "visual_confirmed", "reuse_scope": "affirmation_action_row",
        "bindings": [_binding(["home_today_affirmation"], "action_icon", [218, 662, 42, 42], confidence="user_confirmed_semantics", notes="User confirmed like action semantics.")],
    },
    "controls/control_wifi.png": {
        "role": "system_status_icon", "status": "visual_confirmed", "reuse_scope": "system_bar",
        "bindings": [_binding(SCENE_WITH_STATUS_BAR, "system_bar", [288, 8, 48, 48])],
    },
    "controls/control_wifi_off.png": {
        "role": "connection_failure_icon", "status": "visual_confirmed", "reuse_scope": "hotspot_timeout",
        "bindings": [_binding(["status_hotspot_timeout"], "state_badge_icon", [220, 527, 40, 32], confidence="user_confirmed", notes="Placed over the orange state badge generated by the page spec.")],
    },
    "controls/control_wifi_off_badge.png": {
        "role": "system_status_icon", "status": "unbound", "reuse_scope": "none", "bindings": [],
        "notes": "Do not replace control_wifi_off.png until the compact badge state is visually identified.",
    },
    "moods/mood_calmness.png": {
        "role": "mood_icon", "status": "visual_confirmed", "reuse_scope": "interactive_mood_row",
        "bindings": [_binding(["push_interactive_favorited", "push_interactive_unfavorited"], "mood_option", [73, 664, 37, 37], confidence="user_confirmed_semantics")],
    },
    "moods/mood_good.png": {
        "role": "mood_icon", "status": "visual_confirmed", "reuse_scope": "interactive_mood_row",
        "bindings": [_binding(["push_interactive_favorited", "push_interactive_unfavorited"], "mood_option", [160, 662, 40, 40], confidence="user_confirmed_semantics")],
    },
    "moods/mood_down.png": {
        "role": "mood_icon", "status": "visual_confirmed", "reuse_scope": "interactive_mood_row",
        "bindings": [_binding(["push_interactive_favorited", "push_interactive_unfavorited"], "mood_option", [248, 662, 40, 40], confidence="user_confirmed_semantics")],
    },
    "moods/mood_stressed.png": {
        "role": "mood_icon", "status": "visual_confirmed", "reuse_scope": "interactive_mood_row",
        "bindings": [_binding(["push_interactive_favorited", "push_interactive_unfavorited"], "mood_option", [336, 662, 40, 40], confidence="user_confirmed_semantics")],
    },
    "states/state_empty_favorite.png": {
        "role": "empty_state_illustration", "status": "visual_confirmed", "reuse_scope": "affirmation_empty",
        "bindings": [_binding(["home_affirmation_empty"], "empty_state", [127, 108, 227, 268])],
    },
    "status/status_clock.png": {
        "role": "duration_icon", "status": "visual_confirmed", "reuse_scope": "video_metadata",
        "bindings": [_binding(["push_video_favorited", "push_video_unfavorited"], "video_metadata", [191, 596, 22, 22], confidence="user_confirmed")],
    },
    "status/status_failure_x.png": {
        "role": "failure_state_icon", "status": "visual_confirmed", "reuse_scope": "firmware_failure",
        "bindings": [_binding(["status_firmware_failed"], "state_badge_icon", [225, 531, 31, 31], confidence="user_confirmed", notes="Placed over the red state badge generated by the page spec.")],
    },
    "status/status_loading_vector.png": {
        "role": "loading_state_icon", "status": "visual_confirmed", "reuse_scope": "loading_states",
        "bindings": [_binding(["status_data_loading", "status_device_initial_loading"], "state_badge_icon", [219, 224, 42, 42], confidence="user_confirmed")],
    },
    "status/status_success_check.png": {
        "role": "success_state_icon", "status": "visual_confirmed", "reuse_scope": "success_states",
        "bindings": [_binding(["status_data_synced", "status_reset_complete", "status_wifi_connected"], "state_badge_icon", [216, 532, 48, 48], confidence="user_confirmed")],
    },
}


def _all_design_ids() -> set[str]:
    return {path.stem for path in DESIGN_ROOT.rglob("*.png") if path.name != "debug_overlay.png"}


def build() -> dict[str, Any]:
    source_assets = {path.relative_to(ASSET_ROOT).as_posix() for path in ASSET_ROOT.rglob("*") if path.is_file()}
    if source_assets != set(CURATED):
        missing = sorted(source_assets - set(CURATED))
        stale = sorted(set(CURATED) - source_assets)
        raise ValueError(f"asset matrix inventory mismatch: missing={missing}, stale={stale}")
    design_ids = _all_design_ids()
    assets: list[dict[str, Any]] = []
    page_assets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in sorted(CURATED):
        entry = dict(CURATED[source])
        image = Image.open(ASSET_ROOT / source).convert("RGBA")
        entry["source"] = source
        entry["source_size"] = [image.width, image.height]
        entry["alpha_bbox"] = list(image.getchannel("A").getbbox() or (0, 0, image.width, image.height))
        for binding in entry["bindings"]:
            unknown = sorted(set(binding["page_ids"]) - design_ids)
            if unknown:
                raise ValueError(f"{source} references unknown designs: {unknown}")
            for page_id in binding["page_ids"]:
                page_assets[page_id].append({"source": source, **{key: value for key, value in binding.items() if key != "page_ids"}})
        assets.append(entry)
    pages = []
    for page_id in sorted(design_ids):
        bound = sorted(page_assets.get(page_id, []), key=lambda item: (item["layer"], item["source"]))
        confirmed = {"visual_confirmed", "user_confirmed", "user_confirmed_semantics"}
        pages.append({
            "id": page_id,
            "design_reference": next(path.relative_to(PACKAGE).as_posix() for path in DESIGN_ROOT.rglob(f"{page_id}.png")),
            "bindings": bound,
            "status": "ready_for_spec" if bound and all(item["confidence"] in confirmed for item in bound) else "needs_bbox_refinement",
        })
    return {
        "schema_version": "1.0", "coordinate_space": {"width": 480, "height": 800, "origin": "top_left"},
        "policy": {"automatic_binding": "forbidden", "spec_emission_requires": "visual_confirmed bindings only"},
        "assets": assets, "pages": pages,
        "summary": {
            "asset_count": len(assets),
            "visually_confirmed": sum(asset["status"] == "visual_confirmed" for asset in assets),
            "unbound": sum(asset["status"] == "unbound" for asset in assets),
            "code_drawn": sum(asset["status"] == "code_drawn" for asset in assets),
            "reference_only": sum(asset["status"] == "reference_only" for asset in assets),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "multipage_ui" / "asset_binding_matrix.json")
    args = parser.parse_args()
    result = build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
