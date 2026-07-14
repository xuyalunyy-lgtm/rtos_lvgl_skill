"""Normalize the supplied multi-page UI screenshots and cut assets.

The UI package intentionally uses ASCII-only, stable paths so the Manifest v2.1
contract can be consumed by the LVGL MCP generator on Windows and CI hosts.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "ui"
SOURCE_DESIGNS = UI_ROOT / "page"
SOURCE_CUTS = UI_ROOT / "INITIAL"
PACKAGE_ROOT = UI_ROOT / "multipage"


DESIGN_MAP: tuple[tuple[str, str, str], ...] = (
    ("首页/初始页面.png", "home", "home_default"),
    ("首页/今日Affirmation查收-新.png", "home", "home_today_affirmation"),
    ("首页/Affirmation页面（有收藏）-新.png", "home", "home_affirmation_favorited"),
    ("首页/Affirmation页面（空状态）.png", "home", "home_affirmation_empty"),
    ("首页/Schedule页.png", "home", "home_schedule"),
    ("首页/弹出菜单(无收藏）.png", "home", "home_menu_unfavorited"),
    ("首页/弹出菜单(有收藏）.png", "home", "home_menu_favorited"),
    ("首页/菜单使用引导(无收藏）.png", "home", "home_menu_guide_unfavorited"),
    ("首页/菜单使用引导(有收藏）.png", "home", "home_menu_guide_favorited"),
    ("推送交互/互动场景（无收藏）.png", "push", "push_interactive_unfavorited"),
    ("推送交互/互动场景（有收藏）.png", "push", "push_interactive_favorited"),
    ("推送交互/reminder无交互反馈（无收藏）.png", "push", "push_reminder_unfavorited"),
    ("推送交互/reminder交互反馈（有收藏）.png", "push", "push_reminder_feedback_favorited"),
    ("推送交互/查收Affirmation（无收藏）.png", "push", "push_affirmation_unfavorited"),
    ("推送交互/查收Affirmation（有收藏）.png", "push", "push_affirmation_favorited"),
    ("推送交互/查收视频消息（无收藏）.png", "push", "push_video_unfavorited"),
    ("推送交互/查收视频消息（有收藏）.png", "push", "push_video_favorited"),
    ("状态页/副屏设备 - 初始状态.png", "status", "status_device_initial"),
    ("状态页/副屏设备 - 初始状态-加载中.png", "status", "status_device_initial_loading"),
    ("状态页/Wi-Fi连接成功.png", "status", "status_wifi_connected"),
    ("状态页/副屏设备 - 数据同步中.png", "status", "status_data_syncing"),
    ("状态页/副屏设备 - 数据同步完成.png", "status", "status_data_synced"),
    ("状态页/副屏设备 - 配网失败.png", "status", "status_network_setup_failed"),
    ("状态页/副屏设备 - 热点连接超时（情况B））.png", "status", "status_hotspot_timeout"),
    ("状态页/副屏设备 - 固件更新中.png", "status", "status_firmware_updating"),
    ("状态页/副屏设备 - 固件更新失败.png", "status", "status_firmware_failed"),
    ("状态页/副屏设备 - 重置中.png", "status", "status_resetting"),
    ("状态页/副屏设备 - 重置完成.png", "status", "status_reset_complete"),
    ("状态页/数据loading.png", "status", "status_data_loading"),
)

CUT_MAP: tuple[tuple[str, str, str], ...] = (
    ("home_bg.png", "backgrounds", "background_home"),
    ("home_bg.jpg", "backgrounds", "background_home_source"),
    ("play_bg.png", "backgrounds", "background_player"),
    ("initial_page_pet.png", "characters", "character_pet_idle"),
    ("loading_spirit.png", "characters", "character_loading_spirit"),
    ("player.png", "content", "content_player"),
    ("page_player.png", "content", "content_player_page"),
    ("daily_recommendation_01.png", "content", "content_daily_recommendation_01"),
    ("daily_recommendation_02.png", "content", "content_daily_recommendation_02"),
    ("daily_recommendation_03.png", "content", "content_daily_recommendation_03"),
    ("text_card.png", "content", "content_text_card"),
    ("text_label.png", "content", "content_text_label"),
    ("clock.png", "status", "status_clock"),
    ("success_check.png", "status", "status_success_check"),
    ("fail_x.png", "status", "status_failure_x"),
    ("loading_vector.png", "status", "status_loading_vector"),
    ("icon.png", "controls", "control_primary"),
    ("icon_back.png", "controls", "control_back"),
    ("icon_battery.png", "controls", "control_battery"),
    ("icon_bluetooth.png", "controls", "control_bluetooth"),
    ("icon_bluetooth_off.png", "controls", "control_bluetooth_off"),
    ("icon_wifi.png", "controls", "control_wifi"),
    ("icon_wifi_off.png", "controls", "control_wifi_off"),
    ("icon_wifi_off_badge.png", "controls", "control_wifi_off_badge"),
    ("icon_dislike.png", "controls", "control_dislike"),
    ("icon_favorite.png", "controls", "control_favorite"),
    ("icon_like.png", "controls", "control_like"),
    ("icon_long_press_heart.png", "controls", "control_long_press_heart"),
    ("Thumbs-up (赞)-1.png", "controls", "control_thumb_down"),
    ("Thumbs-up (赞).png", "controls", "control_thumb_up"),
    ("mood_calmness.png", "moods", "mood_calmness"),
    ("mood_down.png", "moods", "mood_down"),
    ("mood_good.png", "moods", "mood_good"),
    ("mood_stressed.png", "moods", "mood_stressed"),
    ("empty_favorite.png", "states", "state_empty_favorite"),
)


def _target_design(group: str, page_id: str) -> Path:
    return PACKAGE_ROOT / "designs" / group / f"{page_id}.png"


def _target_asset(group: str, asset_id: str, source: Path) -> Path:
    return PACKAGE_ROOT / "assets" / group / f"{asset_id}{source.suffix.lower()}"


def _move(source: Path, target: Path, apply: bool) -> str:
    if source.exists():
        if target.exists():
            raise FileExistsError(f"target already exists while source remains: {target}")
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
        return "move"
    if target.exists():
        return "present"
    raise FileNotFoundError(f"source and target are both missing: {source} -> {target}")


def build_manifest() -> dict[str, Any]:
    page_ids = [page_id for _, _, page_id in DESIGN_MAP]
    pages = []
    routes = []
    for index, (_, group, page_id) in enumerate(DESIGN_MAP):
        next_page = page_ids[(index + 1) % len(page_ids)]
        route_id = f"next_{page_id}"
        design = _target_design(group, page_id).relative_to(PACKAGE_ROOT).as_posix()
        pages.append({
            "id": page_id,
            "states": {"default": {"design": design}},
            "nodes": ["root"],
            "events": [{
                "node_id": "root",
                "trigger": "clicked",
                "actions": [{"type": "route", "route_id": route_id}],
            }],
            "quality_regions": [{"kind": "interaction", "id": "screen_tap"}],
        })
        routes.append({
            "id": route_id,
            "from": page_id,
            "to": next_page,
            "mode": "replace",
            "event": "root.clicked",
        })

    assets = {}
    for source_name, group, asset_id in CUT_MAP:
        source = SOURCE_CUTS / source_name
        target = _target_asset(group, asset_id, source)
        assets[asset_id] = {
            "source": target.relative_to(PACKAGE_ROOT).as_posix(),
            "symbol": asset_id,
            "kind": "image",
            "alpha": "auto",
            "format": "auto",
        }

    return {
        "schema_version": "2.1",
        "app": {
            "id": "wellbeing_multipage",
            "entry_page": page_ids[0],
            "navigation": {"mode": "stack", "max_depth": 2},
        },
        "display": {"width": 480, "height": 800, "color_format": "RGB565"},
        "shared": {"assets": assets, "fonts": {}},
        "models": [],
        "pages": pages,
        "routes": routes,
        "flows": [{
            "id": "tap_through_all_pages",
            "start_page": page_ids[0],
            "steps": [{"event": "root.clicked", "expect_page": page_id} for page_id in page_ids[1:]],
        }],
        "memory": {"max_runtime_asset_bytes": 8 * 1024 * 1024, "max_dynamic_heap_bytes": 65536},
        "quality": {"profile": "mvp_90"},
    }


def organize(*, apply: bool) -> dict[str, Any]:
    operations: list[dict[str, str]] = []
    for source_rel, group, page_id in DESIGN_MAP:
        source = SOURCE_DESIGNS / source_rel
        target = _target_design(group, page_id)
        operations.append({"kind": "design", "action": _move(source, target, apply), "target": str(target)})
    for source_name, group, asset_id in CUT_MAP:
        source = SOURCE_CUTS / source_name
        target = _target_asset(group, asset_id, source)
        operations.append({"kind": "asset", "action": _move(source, target, apply), "target": str(target)})

    manifest = build_manifest()
    catalog = {
        "schema_version": "1.0",
        "design_count": len(DESIGN_MAP),
        "asset_count": len(CUT_MAP),
        "designs": [{"source": source, "group": group, "id": page_id} for source, group, page_id in DESIGN_MAP],
        "assets": [{"source": source, "group": group, "id": asset_id} for source, group, asset_id in CUT_MAP],
    }
    if apply:
        PACKAGE_ROOT.mkdir(parents=True, exist_ok=True)
        (PACKAGE_ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        (PACKAGE_ROOT / "asset_catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"operations": operations, "manifest": manifest, "catalog": catalog}


def main() -> int:
    parser = argparse.ArgumentParser(description="Organize multi-page UI source images and create a Manifest v2.1 contract")
    parser.add_argument("--apply", action="store_true", help="move files and write the generated manifest/catalog")
    args = parser.parse_args()
    result = organize(apply=args.apply)
    counts: dict[str, int] = {}
    for item in result["operations"]:
        counts[item["action"]] = counts.get(item["action"], 0) + 1
    print(json.dumps({
        "ok": True,
        "applied": args.apply,
        "design_count": len(DESIGN_MAP),
        "asset_count": len(CUT_MAP),
        "operations": counts,
        "manifest": str(PACKAGE_ROOT / "manifest.json"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
