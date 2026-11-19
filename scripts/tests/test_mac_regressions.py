import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import jy_ui
import panel
import steps
import timeline as tl


class MacTimelineTests(unittest.TestCase):
    def setUp(self):
        tl.L = {"ruler": (0, 50, 1000, 70)}
        tl._cal = (0.0, 0.0, 10.0)

    def test_native_progress_description_parses_exact_frame(self):
        self.assertEqual(68, tl._progress_frames("currentProgress|00:00:02:08"))
        self.assertIsNone(tl._progress_frames("currentProgress"))

    def test_ruler_scale_jump_does_not_replace_good_calibration(self):
        tl._cal = (0.0, 363.0, 44.5)
        tl.L = {"ruler": (0, 50, 2100, 70), "tl": (0, 0, 2100, 500)}
        hits = [(f"00:{s:02d}", s * 100, 60, (s * 100, 55, s * 100 + 40, 65), 1.0)
                for s in (0, 10, 20)]
        with mock.patch.object(jy_ui, "texts", return_value=hits), \
                mock.patch.object(tl.time, "sleep"):
            with self.assertRaises(RuntimeError):
                tl.calibrate()
        self.assertEqual((0.0, 363.0, 44.5), tl._cal)

    def test_seek_zero_never_fakes_success(self):
        with mock.patch.object(jy_ui, "keys"), mock.patch.object(jy_ui, "click"), \
                mock.patch.object(jy_ui, "activate"), mock.patch.object(tl, "read_tc", return_value=11):
            with self.assertRaises(steps.Pause):
                tl.seek(0)

    def test_seek_zero_uses_clickable_ruler_then_verified_steps(self):
        state = {"cur": 90}
        calls = []

        def click(x, _y, **_kwargs):
            if x > 0:
                state["cur"] = 13

        def keys(value, **_kwargs):
            calls.append(value)
            state["cur"] -= 1

        with mock.patch.object(jy_ui, "IS_MAC", True), \
                mock.patch.object(jy_ui, "activate"), \
                mock.patch.object(jy_ui, "click", side_effect=click), \
                mock.patch.object(jy_ui, "keys", side_effect=keys), \
                mock.patch.object(tl, "read_tc", side_effect=lambda: state["cur"]), \
                mock.patch.object(tl.time, "sleep"):
            result = tl.seek(0)
        self.assertLessEqual(abs(result), tl.TOL)
        self.assertEqual(12, len(calls))

    def test_seek_snapping_uses_closest_click_then_verified_steps(self):
        state = {"cur": 52}
        calls = []

        def keys(value, **_kwargs):
            calls.append(value)
            state["cur"] += 1 if value == "{Right}" else -1

        with mock.patch.object(jy_ui, "IS_MAC", True), \
                mock.patch.object(jy_ui, "activate"), \
                mock.patch.object(jy_ui, "click"), \
                mock.patch.object(jy_ui, "keys", side_effect=keys), \
                mock.patch.object(tl, "read_tc", side_effect=lambda: state["cur"]), \
                mock.patch.object(tl.time, "sleep") as sleeps:
            result = tl.seek(2.0)
        self.assertTrue(any(call.args[0] == 0.25 for call in sleeps.call_args_list))
        self.assertLessEqual(abs(result - 60), tl.TOL)
        self.assertEqual(7, len(calls))

    def test_seek_zero_can_drag_playhead_to_start(self):
        state = {"cur": 11}

        def drag(_x1, _y1, _x2, _y2, **_kwargs):
            state["cur"] = 0

        with mock.patch.object(jy_ui, "IS_MAC", True), \
                mock.patch.object(jy_ui, "activate"), \
                mock.patch.object(jy_ui, "click"), \
                mock.patch.object(jy_ui, "keys"), \
                mock.patch.object(jy_ui.auto, "DragDrop", side_effect=drag) as drag_mock, \
                mock.patch.object(tl, "read_tc", side_effect=lambda: state["cur"]), \
                mock.patch.object(tl.time, "sleep"):
            self.assertEqual(0, tl.seek(0))
            drag_mock.assert_called_once()

    def test_seek_zero_home_fallback_is_read_back(self):
        state = {"cur": 11}

        def keys(value, **_kwargs):
            if value == "{Home}":
                state["cur"] = 0

        with mock.patch.object(jy_ui, "IS_MAC", True), \
                mock.patch.object(jy_ui, "activate"), \
                mock.patch.object(jy_ui, "click"), \
                mock.patch.object(jy_ui, "keys", side_effect=keys), \
                mock.patch.object(tl, "read_tc", side_effect=lambda: state["cur"]), \
                mock.patch.object(tl.time, "sleep"):
            self.assertEqual(0, tl.seek(0))

    def test_seek_corrects_clicks_without_frame_key_noise(self):
        state = {"cur": 0}

        def click(x, _y, **_kwargs):
            state["cur"] = max(0, round(x / 10 * 30) - 8)

        def keys(*_args, **_kwargs):
            self.fail("seek should not spray frame keys on Mac")

        with mock.patch.object(jy_ui, "IS_MAC", True), \
                mock.patch.object(jy_ui, "activate"), \
                mock.patch.object(jy_ui, "click", side_effect=click), \
                mock.patch.object(jy_ui, "keys", side_effect=keys), \
                mock.patch.object(tl, "read_tc", side_effect=lambda: state["cur"]), \
                mock.patch.object(tl.time, "sleep"):
            self.assertEqual(60, tl.seek(2.0))


class MacLifecycleTests(unittest.TestCase):
    def test_in_editor_handles_zero_sized_missing_window(self):
        import types
        window = types.SimpleNamespace(BoundingRectangle=types.SimpleNamespace(left=0, top=0, right=0, bottom=0))
        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps.jy_ui, "win", return_value=window), \
                mock.patch.object(steps.jy_ui, "texts") as texts:
            self.assertFalse(steps.in_editor())
            texts.assert_not_called()


class MacJobTests(unittest.TestCase):
    def test_job_can_override_beauty_preset_without_changing_style_file(self):
        import live_run
        with mock.patch.object(live_run.steps, "apply_beauty_preset") as apply:
            live_run.apply_beauty_for_job({"beauty_preset": "自然柔光"}, 3.0)
            apply.assert_called_once_with(3.0, "自然柔光")


class MacOverlayTests(unittest.TestCase):
    def test_mac_overlay_does_not_raise_and_reactivate_each_tick(self):
        import importlib.util
        path = pathlib.Path(__file__).resolve().parent.parent / "overlay" / "overlay.py"
        spec = importlib.util.spec_from_file_location("xy_overlay", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.object(module.osctl, "IS_MAC", True):
            overlay = mock.Mock()
            module.raise_overlay(overlay)
            overlay.raise_.assert_not_called()


class MacScreenTests(unittest.TestCase):
    def test_mac_screen_capture_does_not_call_image_grab(self):
        sentinel = object()
        with mock.patch.object(jy_ui, "IS_MAC", True), \
                mock.patch.object(jy_ui, "_quartz_screen", return_value=sentinel), \
                mock.patch.object(jy_ui.ImageGrab, "grab", side_effect=AssertionError("screencapture path")):
            self.assertIs(sentinel, jy_ui._screen())


class MacMouseTests(unittest.TestCase):
    def test_single_click_has_explicit_click_state(self):
        import Quartz
        events = []
        with mock.patch.object(jy_ui.auto, "_post", side_effect=events.append), \
                mock.patch.object(jy_ui.auto.time, "sleep"), \
                mock.patch.object(Quartz, "CGEventSetIntegerValueField") as set_field:
            jy_ui.auto.Click(100, 100)
        self.assertTrue(any(call.args[1:] == (Quartz.kCGMouseEventClickState, 1)
                            for call in set_field.call_args_list))


class MacTrackTests(unittest.TestCase):
    def test_select_at_waits_for_mac_property_panel(self):
        tl._cal = (0.0, 0.0, 10.0)
        tl.L = {"track_y": 400}
        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps.jy_ui, "click") as click, \
                mock.patch.object(steps, "panel_tabs", side_effect=[[], ["画面"]]) as tabs, \
                mock.patch.object(steps.time, "sleep"):
            steps.select_at(3.0)
            self.assertGreaterEqual(tabs.call_count, 2)
            self.assertEqual(2, click.call_count)

    def test_mac_track_scroll_does_not_zoom_timeline_with_wheel(self):
        tl.L = {"tl": (0, 100, 1000, 500)}
        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps.auto, "MoveTo"), \
                mock.patch.object(steps.auto, "WheelUp") as wheel:
            steps.scroll_tracks_top()
            wheel.assert_not_called()


class MacTextTests(unittest.TestCase):
    def test_native_tab_identifier_maps_to_visible_name(self):
        self.assertEqual("文本", panel._native_tab_name("text_text"))
        self.assertEqual("动画", panel._native_tab_name("text_animation"))
        self.assertEqual("画面", panel._native_tab_name("video_screen"))
        self.assertEqual("美颜美体", panel._native_tab_name("VESettingPanelSubTabControl:美颜美体"))
        self.assertEqual("文本", panel._native_tab_name("root_文本"))
        self.assertEqual("智能字幕", panel._native_tab_name("VETreeSubCellItem:智能字幕"))
        self.assertEqual("美颜预设", panel._native_tab_name("automationbeautyPresetGroup"))

    def test_panel_tabs_prefer_native_values(self):
        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps.panel, "native_tabs", return_value=["画面", "基础", "美颜美体"]), \
                mock.patch.object(steps.panel, "tab_rows") as ocr:
            self.assertIn("画面", steps.panel_tabs())
            ocr.assert_not_called()

    def test_missing_required_font_never_silently_substitutes(self):
        import types
        f = ("字体", 2670, 663, (2642, 646, 2700, 679), 1.0)
        window = types.SimpleNamespace(BoundingRectangle=types.SimpleNamespace(left=0, top=0, right=3380, bottom=2022))
        search = ("搜索字体名称或风格", 2800, 700, (2760, 680, 2900, 720), 1.0)
        native = ("字体", 2990, 660, (2760, 642, 3338, 684), 1.0)
        state = {"open": False}

        def click(x, _y, **_kwargs):
            if (x, _y) == (2990, 663):
                state["open"] = True

        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps, "_font_row", return_value=f), \
                mock.patch.object(steps.panel, "label_column", return_value=(2500, 2900)), \
                mock.patch.object(steps.panel, "_native_tab_hit", return_value=native), \
                mock.patch.object(steps.jy_ui, "win", return_value=window), \
                mock.patch.object(steps.jy_ui, "texts", side_effect=lambda *a, **k: [search] if state["open"] else []), \
                mock.patch.object(steps.jy_ui, "click", side_effect=click) as click, \
                mock.patch.object(steps.jy_ui, "keys") as keys, \
                mock.patch.object(steps.auto, "SetClipboardText"), \
                mock.patch.object(steps.time, "sleep"):
            with self.assertRaises(steps.Pause):
                steps.pick_font("仓耳榜黑")
            self.assertTrue(any(call.args == (2990, 663) for call in click.call_args_list), click.call_args_list)
            self.assertTrue(any(call.args and call.args[0] == "{Enter}" for call in keys.call_args_list))

    def test_tab_uses_native_frame_before_ocr(self):
        hit = ("画面", 2800, 180, (2760, 160, 2840, 200), 1.0)
        with mock.patch.object(steps.panel.auto, "IS_MAC", True), \
                mock.patch.object(steps.panel, "_native_tab_hit", return_value=hit), \
                mock.patch.object(steps.panel.jy_ui, "click") as click, \
                mock.patch.object(steps.panel, "tab_rows") as ocr, \
                mock.patch.object(steps.panel.time, "sleep"):
            steps.panel.tab("画面")
            click.assert_called_once_with(2800, 180)
            ocr.assert_not_called()

    def test_native_tab_waits_for_async_control(self):
        hit = ("画面", 2800, 180, (2760, 160, 2840, 200), 1.0)
        with mock.patch.object(steps.panel.auto, "IS_MAC", True), \
                mock.patch.object(steps.panel, "_native_tab_hit", side_effect=[None, hit]) as native, \
                mock.patch.object(steps.panel.jy_ui, "click"), \
                mock.patch.object(steps.panel.time, "sleep"):
            steps.panel.tab("画面")
            self.assertEqual(2, native.call_count)

    def test_click_text_uses_native_frame_before_ocr(self):
        hit = ("文本", 222, 162, (202, 142, 242, 182), 1.0)
        with mock.patch.object(jy_ui, "IS_MAC", True), \
                mock.patch.object(panel, "_native_tab_hit", return_value=hit), \
                mock.patch.object(jy_ui, "click") as click, \
                mock.patch.object(jy_ui, "find") as ocr:
            jy_ui.click_text("文本")
            click.assert_called_once_with(222, 162)
            ocr.assert_not_called()

    def test_font_search_does_not_click_the_search_box_as_a_result(self):
        import types
        f = ("字体", 2670, 663, (2642, 646, 2700, 679), 1.0)
        window = types.SimpleNamespace(BoundingRectangle=types.SimpleNamespace(left=0, top=0, right=3380, bottom=2022))
        search = ("搜索字体名称或风格", 2841, 736, (2760, 680, 2900, 720), 1.0)
        query = ("新青年体", 2841, 736, (2760, 680, 2900, 720), 1.0)
        result = ("新青年体", 2890, 1042, (2800, 1020, 3000, 1061), 1.0)
        state = {"open": False, "searched": False, "selected": False}
        native = ("字体", 2990, 663, (2760, 642, 3338, 684), 1.0)

        def click(x, y, **_kwargs):
            if (x, y) == (2990, 663):
                state["open"] = True
            if abs(y - 1051) < 2:
                state["selected"] = True

        def texts(*args, **_kwargs):
            if not state["open"]:
                return []
            region = args[0] if args else None
            if region and region[1] < 650 and region[3] < 700:
                return [("新青年体" if state["selected"] else "系统", 2890, 663, (2800, 650, 3000, 680), 1.0)]
            if state["selected"]:
                return [("新青年体", 2890, 663, (2800, 650, 3000, 680), 1.0)]
            return [search] if not state["searched"] else [query, result]

        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps, "_font_row", return_value=f), \
                mock.patch.object(steps.panel, "label_column", return_value=(2500, 2900)), \
                mock.patch.object(steps.panel, "_native_tab_hit", return_value=native), \
                mock.patch.object(steps.jy_ui, "win", return_value=window), \
                mock.patch.object(steps.jy_ui, "texts", side_effect=texts), \
                mock.patch.object(steps.jy_ui, "click", side_effect=click), \
                mock.patch.object(steps.jy_ui, "keys"), \
                mock.patch.object(steps.auto, "SetClipboardText", side_effect=lambda _s: state.update(searched=True)), \
                mock.patch.object(steps.time, "sleep"):
            steps.pick_font("新青年体")
        self.assertTrue(state["selected"])

    def test_native_text_write_waits_for_async_field(self):
        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps, "_native_replace_content", side_effect=[False, True]) as native, \
                mock.patch.object(steps.panel, "tab_rows") as ocr, \
                mock.patch.object(steps.jy_ui, "keys"), \
                mock.patch.object(steps.time, "sleep"):
            steps.replace_content("验收大字")
            self.assertEqual(2, native.call_count)
            ocr.assert_not_called()

    def test_native_text_write_commits_the_edit(self):
        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps, "_native_replace_content", return_value=True), \
                mock.patch.object(steps.auto, "SetClipboardText"), \
                mock.patch.object(steps.jy_ui, "keys") as keys:
            steps.replace_content("验收大字")
            self.assertTrue(any(call.args and call.args[0] == "{Ctrl}v" for call in keys.call_args_list))
            self.assertTrue(any(call.args and call.args[0] == "{Enter}" for call in keys.call_args_list))

    def test_font_row_uses_native_control_when_label_is_occluded(self):
        hit = ("字体", 2990, 660, (2760, 642, 3338, 684), 1.0)
        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps.panel, "_native_tab_hit", return_value=hit), \
                mock.patch.object(steps.jy_ui, "find") as ocr:
            row = steps._font_row()
            self.assertEqual("字体", row[0])
            self.assertEqual(660, row[2])
            ocr.assert_not_called()

    def test_beauty_tab_reclicks_when_preset_content_is_missing(self):
        tab = ("美颜美体", 3200, 270, (3160, 250, 3240, 290), 1.0)

        def native(name):
            return tab if name == "美颜美体" else None

        with mock.patch.object(steps.panel.auto, "IS_MAC", True), \
                mock.patch.object(steps.panel, "_native_tab_hit", side_effect=native), \
                mock.patch.object(steps.panel.jy_ui, "click") as click, \
                mock.patch.object(steps.panel.time, "sleep"):
            steps.panel.tab("美颜美体", sub=True)
            self.assertEqual(2, click.call_count)

    def test_replace_content_prefers_verified_native_text_field(self):
        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps, "_native_replace_content", return_value=True) as native, \
                mock.patch.object(steps.jy_ui, "keys"), \
                mock.patch.object(steps.panel, "tab_rows") as ocr_tabs:
            steps.replace_content("验收大字")
            native.assert_called_once_with("验收大字")
            ocr_tabs.assert_not_called()


class MacPanelTests(unittest.TestCase):
    def test_number_readback_uses_upscaled_ocr(self):
        label = ("字号", 2670, 690, (2645, 675, 2695, 706), 1.0)
        number = ("13", 3248, 690, (3236, 679, 3261, 702), 1.0)

        def texts(_region, upscale=1):
            return [label] if upscale == 1 else [number]

        with mock.patch.object(panel.auto, "IS_MAC", True), \
                mock.patch.object(panel, "label_column", return_value=(2500, 2900)), \
                mock.patch.object(panel.jy_ui, "texts", side_effect=texts):
            _lab, num = panel.row("字号")
            self.assertEqual("13", num[0])

    def test_position_readback_uses_upscaled_ocr(self):
        lab = ("位置", 2670, 500, (2640, 480, 2700, 520), 1.0)
        x = ("X100", 3000, 500, (2970, 485, 3050, 520), 1.0)
        y = ("Y200", 3200, 500, (3170, 485, 3250, 520), 1.0)
        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps.panel, "row", return_value=(lab, None)), \
                mock.patch.object(steps.panel, "scroll"), \
                mock.patch.object(steps.panel, "type_value"), \
                mock.patch.object(steps.jy_ui, "texts", side_effect=lambda _r, upscale=1: [x, y] if upscale == 2 else []):
            steps.set_xy(100, 200)

    def test_number_input_uses_native_frame_when_available(self):
        lab = ("字号", 2670, 690, (2645, 675, 2696, 706), 1.0)
        num = ("13", 3248, 690, (3236, 679, 3261, 702), 1.0)
        with mock.patch.object(panel, "row", return_value=(lab, num)), \
                mock.patch.object(panel, "_native_number_hit", return_value=(3266, 748)), \
                mock.patch.object(panel, "type_value") as type_value:
            panel.set_value("字号", 13)
            self.assertEqual((3266, 748), type_value.call_args.args[:2])

    def test_position_uses_native_boxes_when_ocr_misses_current_values(self):
        lab = ("位置", 2670, 500, (2640, 480, 2700, 520), 1.0)
        boxes = ((2800, 500), (3000, 500))
        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps.panel, "row", return_value=(lab, None)) as row, \
                mock.patch.object(steps, "_native_xy_boxes", return_value=boxes), \
                mock.patch.object(steps.panel, "scroll") as scroll, \
                mock.patch.object(steps.panel, "type_value") as type_value:
            steps.set_xy(100, 200)
            scroll.assert_called()
            self.assertEqual(2, row.call_count)
            self.assertEqual(2800, type_value.call_args_list[0].args[0])
            self.assertEqual(3000, type_value.call_args_list[1].args[0])

    def test_native_hex_value_can_verify_color_input(self):
        with mock.patch.object(steps, "_native_text_values", return_value=["#FFE600"]):
            self.assertTrue(steps._native_text_has("FFE600"))

    def test_text_paste_never_types_without_verified_focus(self):
        with mock.patch.object(panel.auto, "IS_MAC", True), \
                mock.patch.object(panel, "_box_selected", return_value=False), \
                mock.patch.object(panel.jy_ui, "click"), \
                mock.patch.object(panel.jy_ui, "keys") as keys, \
                mock.patch.object(panel.jy_ui, "fx"), \
                mock.patch.object(panel.time, "sleep"):
            with self.assertRaises(steps.Pause):
                panel.type_value(2952, 1571, "FFE600", lambda: False, paste=True)
            self.assertFalse(keys.called)

    def test_position_readback_ignores_ocr_label_noise(self):
        lab = ("位置", 2670, 500, (2640, 480, 2700, 520), 1.0)
        hits = [
            ("X1", 2780, 500, (2760, 485, 2800, 520), 1.0),
            ("1300", 2900, 500, (2860, 485, 2940, 520), 1.0),
            ("0", 3100, 500, (3080, 485, 3120, 520), 1.0),
        ]
        boxes = ((2828, 500), (3024, 500))

        def type_value(_x, _y, _value, ok, **_kwargs):
            if not ok():
                raise steps.Pause("位置读回错误")

        with mock.patch.object(steps.auto, "IS_MAC", True), \
                mock.patch.object(steps.panel, "row", return_value=(lab, None)), \
                mock.patch.object(steps, "_native_xy_boxes", return_value=boxes), \
                mock.patch.object(steps.panel, "scroll"), \
                mock.patch.object(steps.panel, "type_value", side_effect=type_value), \
                mock.patch.object(steps.jy_ui, "texts", return_value=hits):
            steps.set_xy(1300, 0)

    def test_number_input_never_types_without_verified_focus(self):
        with mock.patch.object(panel.auto, "IS_MAC", True), \
                mock.patch.object(panel, "_box_selected", return_value=False), \
                mock.patch.object(panel.jy_ui, "click"), \
                mock.patch.object(panel.jy_ui, "keys") as keys, \
                mock.patch.object(panel.time, "sleep"):
            with self.assertRaises(steps.Pause):
                panel.type_value(3176, 407, 34, lambda: False)
            self.assertFalse(keys.called)

    def test_mac_number_input_uses_select_all_and_paste(self):
        with mock.patch.object(panel.auto, "IS_MAC", True), \
                mock.patch.object(panel, "_box_selected", return_value=True), \
                mock.patch.object(panel.jy_ui, "click"), \
                mock.patch.object(panel.jy_ui, "keys") as keys, \
                mock.patch.object(panel.jy_ui, "fx") as fx, \
                mock.patch.object(panel.auto, "SetClipboardText") as clip, \
                mock.patch.object(panel.time, "sleep"):
            panel.type_value(3176, 407, 34, lambda: True)
            self.assertTrue(any(call.args and call.args[0] == {"type": "clear"} for call in fx.call_args_list))
            clip.assert_called_once_with("34")
            self.assertEqual("{Ctrl}a", keys.call_args_list[0].args[0])
            self.assertTrue(any(call.args[0] == "{Ctrl}v" for call in keys.call_args_list))

    def test_missing_number_bbox_stops_cleanly(self):
        lab = ("强度", 2670, 407, (2642, 390, 2698, 424), 1.0)
        num = (None, 3180, 407, None, None)
        with mock.patch.object(panel, "row", return_value=(lab, num)), \
                mock.patch.object(panel, "type_value", side_effect=steps.Pause("没填进去")):
            with self.assertRaises(steps.Pause):
                panel.set_value("强度", 34)


if __name__ == "__main__":
    unittest.main()
