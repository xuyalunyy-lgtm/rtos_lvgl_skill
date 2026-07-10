#!/usr/bin/env python3
"""SDK 抽象查询引擎 — 为 checker 提供平台无关的 API 查询接口。

Usage:
    from sdk_lookup import SdkLookup
    lookup = SdkLookup("esp32")
    apis = lookup.get_apis("SEM_TAKE")
    regex = lookup.build_regex("SEM_TAKE", "MUTEX_LOCK")

CLI:
    python sdk_lookup.py --platform esp32 --list SEM_TAKE
    python sdk_lookup.py --platform esp32 --category semaphore
    python sdk_lookup.py --platform esp32 --validate-all
    python sdk_lookup.py --validate-constraints
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional

# SDK map 子集解析器；不是通用 YAML loader
sys.path.insert(0, str(Path(__file__).resolve().parent))
from minimal_yaml import safe_load as _yaml_load

# 项目根目录
SKILL_ROOT = Path(__file__).resolve().parent.parent
ABSTRACTION_PATH = SKILL_ROOT / "references" / "sdk_abstraction.yaml"
MAP_DIR = SKILL_ROOT / "platforms"


class SdkLookup:
    """SDK 抽象查询引擎。加载标准操作注册表 + 平台映射，提供查询接口。"""

    def __init__(self, platform: "str | list[str]",
                 abstraction_path: Optional[Path] = None,
                 map_dir: Optional[Path] = None):
        if isinstance(platform, str):
            self.platform = platform
            self.platforms = [platform]
        else:
            self.platform = ",".join(platform)
            self.platforms = list(platform)
        self._abstraction_path = abstraction_path or ABSTRACTION_PATH
        self._map_dir = map_dir or MAP_DIR

        # 加载标准操作注册表
        with open(self._abstraction_path, "r", encoding="utf-8") as f:
            self._registry = _yaml_load(f)

        # 加载平台映射（支持多平台）
        self._platform_maps = []
        for p in self.platforms:
            map_path = self._map_dir / f"{p}_sdk_map.yaml"
            if not map_path.exists():
                raise FileNotFoundError(f"Platform map not found: {map_path}")
            with open(map_path, "r", encoding="utf-8") as f:
                self._platform_maps.append(_yaml_load(f))

        # 单平台时保持兼容
        self._platform_map = self._platform_maps[0] if len(self._platform_maps) == 1 else None

        # 构建操作名 → 映射的索引（多平台聚合）
        self._op_index = {}
        for pmap in self._platform_maps:
            for op_name, op_data in pmap.get("mappings", {}).items():
                if isinstance(op_data, dict):
                    if op_name in self._op_index:
                        # 合并 apis
                        existing = self._op_index[op_name]
                        existing_apis = existing.get("apis", [])
                        new_apis = op_data.get("apis", [])
                        merged_apis = list(dict.fromkeys(existing_apis + new_apis))
                        existing["apis"] = merged_apis
                        # 合并 value（保留所有平台的值）
                        for key in ("value", "cmsis_value", "numeric"):
                            new_val = op_data.get(key)
                            if new_val:
                                existing_vals = existing.get(key)
                                if existing_vals and existing_vals != new_val:
                                    # 转为列表存储多值
                                    if isinstance(existing_vals, list):
                                        if new_val not in existing_vals:
                                            existing_vals.append(new_val)
                                    else:
                                        existing[key] = [existing_vals, new_val]
                    else:
                        self._op_index[op_name] = op_data

        # 构建操作名 → 注册表条目的索引
        self._reg_index = {}
        for category, operations in self._registry.items():
            if isinstance(operations, dict) and category not in ("version", "description"):
                for op_name, op_data in operations.items():
                    if isinstance(op_data, dict):
                        self._reg_index[op_name] = op_data

    def get_apis(self, operation: str) -> list:
        """返回某标准操作在当前平台的具体 API 列表。

        Args:
            operation: 标准操作名，如 "SEM_TAKE", "QUEUE_SEND"

        Returns:
            API 名列表，如 ["xSemaphoreTake"]
        """
        mapping = self._op_index.get(operation, {})
        return mapping.get("apis", [])

    def get_all_apis(self, *operations: str) -> list:
        """返回多个标准操作的所有 API 合并列表。

        Args:
            *operations: 标准操作名

        Returns:
            去重后的 API 名列表
        """
        apis = []
        for op in operations:
            apis.extend(self.get_apis(op))
        return list(dict.fromkeys(apis))  # 保持顺序去重

    def get_all_apis_by_category(self, category: str) -> list:
        """返回某类别下所有操作的 API 合并列表。

        从 sdk_abstraction.yaml 的类别分组中获取操作名列表，
        再通过平台映射查找每个操作的具体 API。

        Args:
            category: 类别名，如 "rtos_semaphore", "rtos_mutex", "memory"

        Returns:
            API 名列表
        """
        operations = self._registry.get(category, {})
        if not isinstance(operations, dict):
            return []
        apis = []
        for op_name, op_data in operations.items():
            if isinstance(op_data, dict):
                apis.extend(self.get_apis(op_name))
        return list(dict.fromkeys(apis))

    def build_regex(self, *operations: str) -> re.Pattern:
        """生成匹配指定操作的正则表达式。

        Args:
            *operations: 标准操作名

        Returns:
            编译后的正则，匹配 API名 + 左括号
        """
        apis = self.get_all_apis(*operations)
        if not apis:
            return re.compile(r"(?!x)x")  # 永远不匹配
        escaped = [re.escape(api) for api in apis]
        pattern = r"\b(?:%s)\s*\(" % "|".join(escaped)
        return re.compile(pattern)

    def build_regex_by_category(self, *categories: str) -> re.Pattern:
        """生成匹配指定类别所有操作的正则。

        Args:
            *categories: 类别名

        Returns:
            编译后的正则
        """
        apis = []
        for cat in categories:
            apis.extend(self.get_all_apis_by_category(cat))
        apis = list(dict.fromkeys(apis))
        if not apis:
            return re.compile(r"(?!x)x")
        escaped = [re.escape(api) for api in apis]
        pattern = r"\b(?:%s)\s*\(" % "|".join(escaped)
        return re.compile(pattern)

    def build_constant_regex(self, *operations: str) -> re.Pattern:
        """生成匹配常量值的正则（如 portMAX_DELAY）。

        Args:
            *operations: 标准操作名（应为常量类操作）

        Returns:
            编译后的正则
        """
        values = []
        for op in operations:
            mapping = self._op_index.get(op, {})
            val = mapping.get("value")
            if val:
                if isinstance(val, list):
                    values.extend(v for v in val if v not in values)
                elif val not in values:
                    values.append(val)
            # 也检查 cmsis_value 等备选
            for key in ("cmsis_value", "numeric"):
                alt = mapping.get(key)
                if alt:
                    if isinstance(alt, list):
                        values.extend(v for v in alt if v not in values)
                    elif alt not in values:
                        values.append(alt)
        if not values:
            return re.compile(r"(?!x)x")
        escaped = [re.escape(v) for v in values]
        pattern = r"\b(?:%s)\b" % "|".join(escaped)
        return re.compile(pattern)

    def get_timeout_infinite(self) -> "str | list[str]":
        """返回平台的永久等待常量。多平台时返回列表。"""
        mapping = self._op_index.get("TIMEOUT_FOREVER", {})
        val = mapping.get("value", "portMAX_DELAY")
        return val

    def get_timeout_zero(self) -> "str | list[str]":
        """返回平台的非阻塞常量。多平台时返回列表。"""
        mapping = self._op_index.get("TIMEOUT_ZERO", {})
        val = mapping.get("value", "0")
        return val

    def get_isr_variant(self, operation: str) -> Optional[str]:
        """返回某操作的 ISR 安全变体 API 名。

        Args:
            operation: 标准操作名

        Returns:
            ISR 变体 API 名，或 None
        """
        mapping = self._op_index.get(operation, {})
        return mapping.get("isr_variant")

    def is_isr_safe(self, operation: str) -> bool:
        """检查某操作是否 ISR 安全。"""
        mapping = self._op_index.get(operation, {})
        return mapping.get("isr_safe", False)

    def get_hint(self, operation: str, hint: str) -> bool:
        """检查操作是否有某 checker hint。"""
        reg_entry = self._reg_index.get(operation, {})
        hints = reg_entry.get("checker_hints", [])
        return hint in hints

    def get_operation_info(self, operation: str) -> dict:
        """返回操作的完整信息（注册表 + 平台映射合并）。"""
        reg = self._reg_index.get(operation, {})
        mapping = self._op_index.get(operation, {})
        return {**reg, **mapping, "operation": operation}

    def list_operations(self) -> list:
        """列出所有已注册的标准操作名。"""
        return list(self._reg_index.keys())

    def list_categories(self) -> list:
        """列出平台映射中的所有类别。"""
        cats = set()
        for pmap in self._platform_maps:
            cats.update(pmap.get("mappings", {}).keys())
        return list(cats)

    @property
    def platform_info(self) -> dict:
        """返回平台基本信息。多平台时返回第一个平台的信息。"""
        pmap = self._platform_maps[0]
        return {
            "platform": self.platform,
            "sdk": pmap.get("sdk"),
            "rtos": pmap.get("rtos"),
        }

    def validate(self) -> list:
        """验证平台映射的完整性。

        Returns:
            问题列表，每项为 (operation, issue_description)
        """
        issues = []
        for op_name in self._reg_index:
            mapping = self._op_index.get(op_name)
            if mapping is None:
                issues.append((op_name, "未在平台映射中定义"))
            elif mapping.get("unsupported"):
                continue  # 平台明确标记为不支持，跳过
            elif not mapping.get("apis") and not mapping.get("value"):
                issues.append((op_name, "apis 和 value 均为空"))
        return issues

    def build_combined_regex(self, pattern: str, *operations: str) -> re.Pattern:
        """将已有正则的核心 alternation 与 lookup API 合并。

        用于将平台特定的正则模式与 SDK lookup 结果合并。

        Args:
            pattern: 原始正则的核心 alternation 部分（如 "vTaskDelay|osDelay|k_sleep"）
            *operations: 标准操作名

        Returns:
            合并后的编译正则
        """
        apis = self.get_all_apis(*operations)
        all_names = list(dict.fromkeys(apis + [n.strip() for n in pattern.split("|") if n.strip()]))
        if not all_names:
            return re.compile(r"(?!x)x")
        escaped = [re.escape(n) for n in all_names]
        return re.compile(r"\b(?:%s)\s*\(" % "|".join(escaped))


def validate_all_platforms():
    """验证所有平台的映射完整性。"""
    platforms = ["esp32", "stm32", "jl", "bk", "zephyr"]
    total_issues = 0
    for platform in platforms:
        try:
            lookup = SdkLookup(platform)
            issues = lookup.validate()
            if issues:
                print(f"\n[{platform}] {len(issues)} 个问题:")
                for op, issue in issues:
                    print(f"  {op}: {issue}")
                total_issues += len(issues)
            else:
                print(f"[{platform}] OK")
        except Exception as e:
            print(f"[{platform}] 加载失败: {e}")
            total_issues += 1
    return total_issues


def validate_constraints():
    """验证约束文档中的标准操作名是否都在注册表中。"""
    lookup = SdkLookup("esp32")  # 只需注册表，不依赖平台
    all_ops = set(lookup.list_operations())

    constraint_path = SKILL_ROOT / "references" / "constraint_detail.md"
    if not constraint_path.exists():
        print("constraint_detail.md 未找到")
        return 1

    content = constraint_path.read_text(encoding="utf-8")
    # 查找大写操作名模式（如 SEM_TAKE, QUEUE_SEND）
    found_ops = set(re.findall(r"\b([A-Z][A-Z_]+(?:_OP)?)\b", content))
    # 过滤掉非操作名的全大写词
    noise = {"P0", "P1", "P2", "ISR", "DMA", "NVS", "OTA", "GPIO", "I2C", "SPI",
             "ADC", "PWM", "LCD", "LED", "USB", "CPU", "RAM", "ROM", "SDK",
             "WDT", "TLS", "SSL", "TCP", "UDP", "HTTP", "MQTT", "JSON",
             "LVGL", "RTOS", "RTOS_HEAP_ALLOC", "PSRAM", "SPIRAM", "SRAM",
             "UV", "RGB", "YUV", "PTS", "AEC", "ASR", "TTS", "I2S",
             "IRQ", "IPC", "SNTP", "DNS", "DHCP", "WiFi", "Kconfig",
             "CONFIG", "FEATURE", "DEBUG", "BOARD", "PLATFORM", "APP_TEST_MODE",
             "LOG_E", "LOG_W", "LOG_I", "LOG_D", "LOG_V", "LOG_", "LOGI",
             "ESP_LOGE", "ESP_LOGW", "ESP_LOGI", "ESP_LOGD", "ESP_LOGV",
             "BK_LOGI", "BK_LOGW", "BK_LOGE",
             # 通用噪音：配置前缀、HAL 前缀、协议缩写、模块名、状态名
             "CONFIG_", "HAL_", "MODULE", "MODULE_ERR_", "MODULE_FEATURE_VALUE",
             "TAG", "STATE", "ERROR", "WARN", "READY", "OVERFLOW", "STACK",
             "IDLE", "STOPPING", "FINISHED", "SECRET", "PASSWORD", "TOKEN",
             "URL", "SSH", "HTTPS", "IP", "ID", "MAX", "NULL",
             "IO", "UI", "PC", "SD", "FS", "RTC", "DAC", "TX", "LR",
             "AAC", "PCM", "MIC", "DRDY", "TE", "REFRESH_RATE",
             "PIR", "BL_EN", "BL_PIN", "OLED_ADDR",
             "WSS", "NET", "TEMP_FIX", "PRIO_LVGL", "PRIO_WSS",
             "PLAYBACK_SLOT", "WHO_AM_I", "SO_RCVTIMEO", "EVT_WSS_CONNECT_FAIL",
             "WIFI_RECONNECT_BASE_MS", "WSS_MAX_RETRY_COUNT",
             "CONFIG_FREERTOS_USE_TICKLESS_IDLE", "CONFIG_LOG_NETWORK_LEVEL",
             "CONFIG_LOG_PROFILE_PROD", "CONFIG_SUBSTITUTE_FILE", "CONFIG_FEATURE_AUDIO",
             "NET_MODE_OFFLINE", "LOG_RATE_LIMIT_MS", "CPHA", "CPOL",
             "AI", "BK", "JL",
             "API", "API_KEY", "APP_TEST_MODE_", "LOG", "UART", "WAIT_FOREVER"}
    found_ops -= noise

    missing = found_ops - all_ops
    if missing:
        print(f"约束文档中 {len(missing)} 个操作名未在注册表中:")
        for op in sorted(missing):
            print(f"  {op}")
        return 1
    else:
        print(f"约束文档中所有操作名均已注册 ({len(found_ops)} 个)")
        return 0


def main():
    parser = argparse.ArgumentParser(description="SDK 抽象查询引擎")
    parser.add_argument("--platform", default="esp32",
                        choices=["esp32", "stm32", "jl", "bk", "zephyr"],
                        help="目标平台")
    parser.add_argument("--list", nargs="+", metavar="OP",
                        help="查询指定操作的 API 列表")
    parser.add_argument("--category", help="查询指定类别的所有 API")
    parser.add_argument("--regex", nargs="+", metavar="OP",
                        help="生成匹配指定操作的正则")
    parser.add_argument("--info", metavar="OP",
                        help="显示操作的完整信息")
    parser.add_argument("--all-ops", action="store_true",
                        help="列出所有标准操作名")
    parser.add_argument("--all-categories", action="store_true",
                        help="列出所有类别")
    parser.add_argument("--validate-all", action="store_true",
                        help="验证所有平台映射完整性")
    parser.add_argument("--validate-constraints", action="store_true",
                        help="验证约束文档中的操作名")
    parser.add_argument("--self-test", action="store_true",
                        help="运行自测")

    args = parser.parse_args()

    if args.validate_all:
        return validate_all_platforms()

    if args.validate_constraints:
        return validate_constraints()

    if args.self_test:
        return run_self_test()

    lookup = SdkLookup(args.platform)
    info = lookup.platform_info
    print(f"Platform: {info['platform']} | SDK: {info['sdk']} | RTOS: {info['rtos']}")

    if args.all_ops:
        for op in lookup.list_operations():
            apis = lookup.get_apis(op)
            print(f"  {op}: {apis}")
        return 0

    if args.all_categories:
        for cat in lookup.list_categories():
            apis = lookup.get_all_apis_by_category(cat)
            print(f"  {cat}: {apis}")
        return 0

    if args.list:
        for op in args.list:
            apis = lookup.get_apis(op)
            print(f"  {op}: {apis}")
        return 0

    if args.category:
        apis = lookup.get_all_apis_by_category(args.category)
        print(f"  {args.category}: {apis}")
        return 0

    if args.regex:
        regex = lookup.build_regex(*args.regex)
        print(f"  Pattern: {regex.pattern}")
        return 0

    if args.info:
        info = lookup.get_operation_info(args.info)
        for k, v in info.items():
            print(f"  {k}: {v}")
        return 0

    parser.print_help()
    return 0


def run_self_test():
    """运行 sdk_lookup 自测。"""
    passed = 0
    failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            print(f"  FAIL: {name}")

    # 测试 ESP32 平台
    print("\n=== ESP32 平台测试 ===")
    esp = SdkLookup("esp32")

    check("ESP32 SEM_TAKE", esp.get_apis("SEM_TAKE") == ["xSemaphoreTake"])
    check("ESP32 QUEUE_SEND", len(esp.get_apis("QUEUE_SEND")) > 0)
    check("ESP32 TIMEOUT_FOREVER", esp.get_timeout_infinite() == "portMAX_DELAY")
    check("ESP32 ISR variant", esp.get_isr_variant("SEM_GIVE") == "xSemaphoreGiveFromISR")
    check("ESP32 not ISR safe SEM_TAKE", not esp.is_isr_safe("SEM_TAKE"))
    check("ESP32 build_regex", "xSemaphoreTake" in esp.build_regex("SEM_TAKE").pattern)
    check("ESP32 hint must_have_timeout", esp.get_hint("SEM_TAKE", "must_have_timeout"))
    check("ESP32 hint isr_forbidden", esp.get_hint("SEM_TAKE", "isr_forbidden"))
    check("ESP32 platform_info", esp.platform_info["platform"] == "esp32")

    # 测试 Zephyr 平台
    print("\n=== Zephyr 平台测试 ===")
    zep = SdkLookup("zephyr")

    check("Zephyr SEM_TAKE", zep.get_apis("SEM_TAKE") == ["k_sem_take"])
    check("Zephyr TIMEOUT_FOREVER", zep.get_timeout_infinite() == "K_FOREVER")
    check("Zephyr ISR safe SEM_TAKE", zep.is_isr_safe("SEM_TAKE"))
    check("Zephyr TASK_CREATE", "k_thread_create" in zep.get_apis("TASK_CREATE"))

    # 测试 BK 平台
    print("\n=== BK 平台测试 ===")
    bk = SdkLookup("bk")

    check("BK SEM_TAKE", bk.get_apis("SEM_TAKE") == ["rtos_get_semaphore"])
    check("BK TIMEOUT_FOREVER", bk.get_timeout_infinite() == "BEKEN_WAIT_FOREVER")
    check("BK HEAP_ALLOC", "rtos_malloc" in bk.get_apis("HEAP_ALLOC"))

    # 测试 JL 平台
    print("\n=== JL 平台测试 ===")
    jl = SdkLookup("jl")

    check("JL SEM_TAKE", jl.get_apis("SEM_TAKE") == ["os_sem_pend"])
    check("JL TASK_CREATE", "thread_fork" in jl.get_apis("TASK_CREATE"))

    # 测试 STM32 平台
    print("\n=== STM32 平台测试 ===")
    stm = SdkLookup("stm32")

    check("STM32 SEM_TAKE", "xSemaphoreTake" in stm.get_apis("SEM_TAKE"))
    check("STM32 GPIO_SET", "HAL_GPIO_WritePin" in stm.get_apis("GPIO_SET"))

    # 测试跨平台一致性
    print("\n=== 跨平台一致性测试 ===")
    all_platforms = [esp, zep, bk, jl, stm]
    for p in all_platforms:
        ops = p.list_operations()
        check(f"{p.platform} 操作数 > 50", len(ops) > 50)

    # 测试验证功能
    print("\n=== 验证功能测试 ===")
    esp_issues = esp.validate()
    check("ESP32 无验证问题", len(esp_issues) == 0)

    # 测试多操作正则
    print("\n=== 多操作正则测试 ===")
    multi_regex = esp.build_regex("SEM_TAKE", "MUTEX_LOCK", "QUEUE_RECV")
    check("多操作正则包含所有 API",
          "xSemaphoreTake" in multi_regex.pattern and
          "xQueueReceive" in multi_regex.pattern)

    # 测试类别查询
    print("\n=== 类别查询测试 ===")
    sem_apis = esp.get_all_apis_by_category("rtos_semaphore")
    check("ESP32 semaphore 类别非空", len(sem_apis) > 0)

    # 总结
    print(f"\n{'='*40}")
    print(f"自测结果: {passed} 通过, {failed} 失败")
    if failed:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
