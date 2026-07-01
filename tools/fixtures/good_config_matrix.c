/**
 * @file good_config_matrix.c
 * @brief C39 配置矩阵 self-test 正例 fixture
 */

/* 正例: #ifdef 使用已知前缀 */
#ifdef CONFIG_APP_FEATURE_AUDIO
    /* 音频功能 */
#endif

#ifdef BOARD_HAS_DISPLAY
    /* 显示功能 */
#endif

#ifdef APP_TEST_MODE_NETWORK
    /* 网络测试模式 */
#endif
