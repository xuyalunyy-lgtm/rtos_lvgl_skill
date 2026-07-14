from mcp.lvgl_compile_gate import _check_brace_balance


def test_brace_check_selects_the_active_lvgl_font_initializer_branch():
    code = """
    #if LVGL_VERSION_MAJOR >= 8
    const int font = {
    #else
    int font = {
    #endif
        .value = 1,
    };
    """

    assert _check_brace_balance(code, "v9")["balanced"] is True
    assert _check_brace_balance(code, "v8")["balanced"] is True


def test_brace_check_still_rejects_an_unclosed_active_branch():
    code = """
    #if LVGL_VERSION_MAJOR >= 8
    const int font = {
    #else
    int font = { 1 };
    #endif
    """

    assert _check_brace_balance(code, "v9")["balanced"] is False
