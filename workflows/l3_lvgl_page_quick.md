# L3 LVGL 页面快速工作流

当目标固件工程已有可用的 LVGL 构建与显示驱动时，使用此精简路径实现一个已确认的小型 LVGL 页面。

1. 从 [页面规划模板](../templates/lvgl_page_plan.json) 摘取当前页面的显示预算、UI owner、状态、资源策略和导航 guard；多页或动态页面必须先运行 `python tools/lvgl_page_plan_checker.py lvgl_page_plan.json`。
2. 动态 UI 使用 LVGL 控件；仅在能显著提升视觉还原度时保留图片资源。
3. 重复分组优先使用 Flex 或 Grid；固定坐标还原须在代码旁说明原因。
4. 构建并运行目标工程，在目标显示设备或模拟器检查裁切、字体回退、触摸处理和任务安全问题。

快速路径不生成由本仓库管理的生成器产物；页面的编译、渲染和打包仍由目标工程负责。
