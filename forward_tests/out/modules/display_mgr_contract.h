/**
 * @file display_mgr_contract.h
 * @brief display_mgr 模块契约（C29 + C30 自动生成）
 *
 * 约束覆盖：
 *   C29.1 — 可调用上下文声明
 *   C29.2 — 阻塞语义声明
 *   C29.3 — 所有权声明
 *   C29.4 — 生命周期顺序声明
 *   C29.5 — 错误码语义声明
 *   C30.1 — 任务/队列拓扑表
 */

#ifndef DISPLAY_MGR_CONTRACT_H
#define DISPLAY_MGR_CONTRACT_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ========================================================================== */
/* 错误码 (C29.5)                                                            */
/* ========================================================================== */

typedef enum {
    DISPLAY_MGR_OK = 0,
    DISPLAY_MGR_ERR_TIMEOUT,      /* 可恢复：超时 */
    DISPLAY_MGR_ERR_RESOURCE,     /* 可恢复：资源不足 */
    DISPLAY_MGR_ERR_CONFIG,       /* 不可恢复：配置错误 */
    DISPLAY_MGR_ERR_IO,           /* 可恢复：IO 错误 */
    DISPLAY_MGR_ERR_STATE,        /* 不可恢复：非法状态 */
} display_mgr_err_t;

/* ========================================================================== */
/* 模块状态 (C32.1 可观测性)                                                 */
/* ========================================================================== */

typedef enum {
    DISPLAY_MGR_STATE_UNINIT = 0,
    DISPLAY_MGR_STATE_IDLE,
    DISPLAY_MGR_STATE_RUNNING,
    DISPLAY_MGR_STATE_STOPPING,
    DISPLAY_MGR_STATE_ERROR,
} display_mgr_state_t;

typedef struct {
    display_mgr_state_t state;
    display_mgr_err_t   last_error;
    uint32_t       last_error_line;
    uint32_t       timeout_count;
    uint32_t       drop_count;
} display_mgr_status_t;

/* ========================================================================== */
/* 模块契约 (C29)                                                            */
/* ========================================================================== */

/**
 * @brief 初始化模块
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 最大等待 100ms
 * @par 生命周期 (C29.4): 必须在 start 之前调用
 *
 * @return DISPLAY_MGR_OK 成功
 * @return DISPLAY_MGR_ERR_RESOURCE 资源不足
 * @return DISPLAY_MGR_ERR_CONFIG 配置错误
 */
display_mgr_err_t display_mgr_init(void);

/**
 * @brief 启动模块
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 非阻塞
 * @par 生命周期 (C29.4): 必须在 init 之后、stop 之前调用
 *
 * @return DISPLAY_MGR_OK 成功
 * @return DISPLAY_MGR_ERR_STATE 未初始化
 */
display_mgr_err_t display_mgr_start(void);

/**
 * @brief 停止模块
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 最大等待 500ms（等待任务退出）
 * @par 可重入 (C29.4): 可重入，多次调用安全
 * @par 生命周期 (C29.4): 可在 start 后任意时刻调用
 *
 * @return DISPLAY_MGR_OK 成功
 */
display_mgr_err_t display_mgr_stop(void);

/**
 * @brief 反初始化模块
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 非阻塞
 * @par 可重入 (C29.4): 可重入，多次调用安全
 * @par 生命周期 (C29.4): 必须在 stop 之后调用
 *
 * @return DISPLAY_MGR_OK 成功
 */
display_mgr_err_t display_mgr_deinit(void);

/**
 * @brief 获取模块状态
 *
 * @par 可调用上下文 (C29.1): task / ISR / timer
 * @par 阻塞语义 (C29.2): 非阻塞
 *
 * @param[out] status 模块状态
 * @return DISPLAY_MGR_OK 成功
 */
display_mgr_err_t display_mgr_get_status(display_mgr_status_t *status);

/* ========================================================================== */
/* 输入/输出接口 (C29.3 所有权)                                              */
/* ========================================================================== */

/**
 * @brief 输入 data
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 最大等待 50ms
 * @par 所有权 (C29.3): 调用方拥有数据，模块内部拷贝
 *
 * @param data 输入数据
 * @param len 数据长度
 * @return DISPLAY_MGR_OK 成功
 * @return DISPLAY_MGR_ERR_TIMEOUT 队列满
 */
display_mgr_err_t display_mgr_input(const void *data, size_t len);

/**
 * @brief 输出 result
 *
 * @par 可调用上下文 (C29.1): task only
 * @par 阻塞语义 (C29.2): 非阻塞
 * @par 所有权 (C29.3): 模块拥有输出数据，调用方只读
 *
 * @param[out] data 输出数据指针
 * @param[out] len 数据长度
 * @return DISPLAY_MGR_OK 成功
 * @return DISPLAY_MGR_ERR_STATE 无数据
 */
display_mgr_err_t display_mgr_output(const void **data, size_t *len);

/* ========================================================================== */
/* 任务拓扑表 (C30)                                                          */
/* ========================================================================== */

/*
 * 任务拓扑表（C30.1）
 *
 * | 任务名 | 优先级 | 栈大小 | 队列 | 生产者 | 消费者 | 超时 | 背压 |
 * |--------|--------|--------|------|--------|--------|------|------|
 * | display_mgr_worker | 5 | 4096 | display_mgr_q (depth=8) | display_mgr_input | display_mgr_process | 50ms | drop-oldest |
 *
 * 队列元素类型: 内部 buffer 描述符（非裸指针）
 * 退出条件: stop flag + k_msgq_purge
 */

#ifdef __cplusplus
}
#endif

#endif /* DISPLAY_MGR_CONTRACT_H */
