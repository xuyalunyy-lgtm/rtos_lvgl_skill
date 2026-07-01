/**
 * @file bad_config_matrix.c
 * @brief C39 配置矩阵 self-test 反例 fixture
 */

/* 反例 C39.3: 无名 #ifdef */
#ifdef TEMP_FIX
    /* 临时修复，未归类 */
#endif

#ifdef MY_DEBUG
    /* 调试宏，未归类 */
#endif

#ifdef ENABLE_FEATURE_X
    /* 功能宏，未归类 */
#endif
