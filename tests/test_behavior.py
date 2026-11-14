from datetime import datetime, timedelta
from pet.behavior import Behavior, PRIORITY_AUTO, PRIORITY_MODULE, PRIORITY_USER
from pet.config import DEFAULTS

# 待机随机小动作可能落到的状态（`_AUTO_ACTIONS` 各分类的大写名）
_AUTO_STATES = ("WANDER", "SAD", "BATH", "CRY", "ANXIOUS", "SURPRISE")


class FakeSprite:
    def __init__(self): self.played = []; self.frozen = False
    def play(self, category): self.played.append(category); return True
    def freeze(self): self.frozen = True
    def unfreeze(self): self.frozen = False


class NoSleepSprite(FakeSprite):
    """除 `sleep` 外都有素材（线上 `sleep` 分类目前是空的）。"""

    def play(self, category):
        self.played.append(category)
        return category != "sleep"


class Clock:
    def __init__(self): self.now = datetime(2026, 10, 20, 9, 0, 0)
    def __call__(self): return self.now
    def adv(self, **kw): self.now += timedelta(**kw)


def make():
    clock, sp = Clock(), FakeSprite()
    b = Behavior(sp, DEFAULTS, clock=clock)
    b.start()
    return b, sp, clock


def test_starts_in_idle_playing_idle(qapp):
    b, sp, _ = make()
    assert b.state == "IDLE" and sp.played[-1] == "idle"


def test_module_event_overrides_auto_and_blocks_lower(qapp):
    b, sp, _ = make()
    b.request("walk", PRIORITY_AUTO)
    assert b.request("eat", PRIORITY_MODULE) is True and b.state == "EAT"
    assert b.request("walk", PRIORITY_AUTO) is False and b.state == "EAT"


def test_user_overrides_auto_but_not_module(qapp):
    b, sp, _ = make()
    b.request("bath", PRIORITY_AUTO)
    assert b.request("happy", PRIORITY_USER) is True and b.state == "HAPPY"
    b.request("eat", PRIORITY_MODULE)
    assert b.request("happy", PRIORITY_USER) is False and b.state == "EAT"


def test_event_state_returns_to_idle_on_finish_or_timeout(qapp):
    b, sp, clock = make()
    b.request("eat", PRIORITY_MODULE, once=True)
    b.on_play_finished("eat")
    assert b.state == "IDLE"
    b.request("eat", PRIORITY_MODULE, once=True, max_ms=3000)
    clock.adv(seconds=4); b.tick(clock())
    assert b.state == "IDLE"


def test_drag_plays_move_and_beats_module(qapp):
    b, sp, _ = make()
    b.request("eat", PRIORITY_MODULE)
    b.on_drag_started()
    assert b.state == "DRAGGED" and sp.played[-1] == "move"
    b.request("walk", PRIORITY_AUTO)
    assert b.state == "DRAGGED"
    b.on_drag_finished()
    assert b.state == "IDLE" and sp.frozen is False


def test_drag_freezes_current_frame_when_move_is_missing(qapp):
    """没有「被拎起来」的素材时定格当前那一帧，而不是换成占位图。"""

    class NoMoveSprite(FakeSprite):
        def play(self, category):
            return False if category == "move" else super().play(category)

    clock, sp = Clock(), NoMoveSprite()
    b = Behavior(sp, DEFAULTS, clock=clock)
    b.start()
    b.on_drag_started()
    assert b.state == "DRAGGED" and sp.frozen is True


def test_waking_from_sleep_plays_awake_once(qapp):
    """睡觉时被叫醒：先插播一次「醒觉」，播完再回待机。"""
    b, sp, _ = make()
    b.request("sleep", PRIORITY_AUTO, once=False)
    assert b.state == "SLEEP"
    b.on_user_click()
    assert b.state == "AWAKE" and sp.played[-1] == "awake"
    b.on_play_finished("awake")
    assert b.state == "IDLE" and sp.played[-1] == "idle"


def test_awake_ends_by_timer_when_the_asset_keeps_looping(qapp):
    """「醒觉」素材是可循环的（不会自己播完），靠状态计时器兜底回待机。"""
    b, sp, clock = make()
    b.request("sleep", PRIORITY_AUTO, once=False)
    b.request("happy", PRIORITY_USER, once=True, max_ms=3000)
    clock.adv(seconds=4); b.tick(clock())
    assert b.state == "IDLE"
    assert sp.played[-3:] == ["happy", "awake", "idle"]


def test_showup_is_followed_by_surprise(qapp):
    """刚露面：`showup` 播完接一个「惊喜」，再回待机。"""
    b, sp, _ = make()
    assert b.play_showup() is True
    assert b.state == "SHOWUP" and sp.played[-1] == "showup"
    b.on_play_finished("showup")
    assert b.state == "SURPRISE" and sp.played[-1] == "surprise"
    b.on_play_finished("surprise")
    assert b.state == "IDLE"


def test_focus_mode_swaps_the_idle_category(qapp):
    """番茄钟专注期间待机素材换成 `think`，退出专注再换回 `idle`。"""
    b, sp, _ = make()
    b.set_idle_category("think")
    assert b.state == "THINK" and sp.played[-1] == "think"
    b.set_idle_category("idle")
    assert b.state == "IDLE" and sp.played[-1] == "idle"


def test_focus_mode_keeps_the_idle_machinery_alive(qapp):
    """换成 `think` 后仍会到点自己触发小动作，不能把待机逻辑冻住。"""
    b, sp, clock = make()
    b.set_idle_category("think")
    b.force_wander_chance(0.0)  # 专测待机小动作：别掷成睡觉
    clock.adv(seconds=DEFAULTS["pet"]["state_intervals"]["idle_to_wander"][1] + 1)
    b.tick(clock())
    assert b.state in _AUTO_STATES


def test_click_plays_happy_once_and_fast_click_plays_angry(qapp):
    b, sp, _ = make()
    b.on_user_click()
    assert b.state == "HAPPY" and sp.played[-1] == "happy"
    b.on_fast_click()
    assert b.state == "ANGRY"


def test_single_shot_sleep_asset_wakes_up_then_returns_to_idle(qapp):
    """睡觉素材标了「只播一次」时，播完等于睡醒：先演一次「醒觉」再回待机。"""
    b, sp, _ = make()
    b.request("sleep", PRIORITY_AUTO, once=False)
    b.on_play_finished("sleep")
    assert b.state == "AWAKE" and sp.played[-1] == "awake"
    b.on_play_finished("awake")
    assert b.state == "IDLE" and sp.played[-1] == "idle"


def test_single_shot_idle_asset_keeps_playing_idle(qapp):
    """待机素材只播一次时接着挑下一个待机素材，画面不会停在末帧。"""
    b, sp, _ = make()
    b.on_play_finished("idle")
    assert b.state == "IDLE" and sp.played[-1] == "idle"


def test_single_shot_stroll_asset_does_not_cut_the_walk_short(qapp):
    """散步素材只播一次也不能半路停下：一圈走完由 `on_stroll_finished` 收尾。"""
    b, sp, _ = make()
    b.request("stroll", PRIORITY_MODULE, once=False)
    b.on_play_finished("stroll")
    assert b.state == "STROLL"


def test_play_finished_from_a_stale_category_is_ignored(qapp):
    """已经被别的高优先级状态顶掉后，旧分类的「播完」不该把状态拽回待机。"""
    b, sp, _ = make()
    b.request("eat", PRIORITY_MODULE)
    b.on_drag_started()
    b.on_play_finished("eat")
    assert b.state == "DRAGGED"


def test_auto_wander_after_interval_and_user_activity_resets_sleep_timer(qapp):
    b, sp, clock = make()
    b.force_wander_chance(0.0)  # 先专测待机小动作：别掷成睡觉
    clock.adv(seconds=DEFAULTS["pet"]["state_intervals"]["idle_to_wander"][1] + 1)
    b.tick(clock())
    assert b.state in _AUTO_STATES   # 待机小动作：走 / 难过 / 洗澡 / 哭 / 焦虑 / 惊喜
    b.on_user_click(); b.on_play_finished("happy")
    b.force_wander_chance(1.0)      # 之后固定成「掷到睡觉」，验证 800s 还没到点
    clock.adv(seconds=800); b.tick(clock())
    assert b.state != "SLEEP"      # 用户操作重置了睡眠计时：800s < 900s 不应入睡


def test_sleep_after_long_idle(qapp):
    """待机超过 `idle_to_sleep` 后入睡（把随机判定固定成必睡）。"""
    b, sp, clock = make()
    b.force_wander_chance(1.0)
    clock.adv(seconds=DEFAULTS["pet"]["state_intervals"]["idle_to_sleep"] + 1)
    b.tick(clock())
    assert b.state == "SLEEP"


def test_missing_sleep_asset_keeps_the_calm_cadence(qapp):
    """没有睡觉素材时，不能每 tick 重掷：否则待满 15 分钟后动作会一个接一个连播。"""
    clock, sp = Clock(), NoSleepSprite()
    b = Behavior(sp, DEFAULTS, clock=clock)
    b.start()
    b.force_wander_chance(0.0)  # 固定成「掷到不睡」

    clock.adv(seconds=DEFAULTS["pet"]["state_intervals"]["idle_to_sleep"] + 1)
    for _ in range(50):
        b.tick(clock())
    assert b.state == "IDLE"  # 仍按 idle_to_wander 的节奏，没有连环换动作

    clock.adv(seconds=DEFAULTS["pet"]["state_intervals"]["idle_to_wander"][1] + 1)
    b.tick(clock())
    assert b.state in _AUTO_STATES


def test_auto_action_skips_categories_without_assets(qapp):
    """抽到的分类没素材（`sad` / `bath` 现在都是空的）就接着抽下一个，不能白等一整个间隔。"""
    class SparseSprite(FakeSprite):
        def play(self, category):
            self.played.append(category)
            return category == "walk"

    clock, sp = Clock(), SparseSprite()
    b = Behavior(sp, DEFAULTS, clock=clock)
    b.start()
    b.force_wander_chance(0.0)  # 别掷成睡觉

    clock.adv(seconds=DEFAULTS["pet"]["state_intervals"]["idle_to_wander"][1] + 1)
    b.tick(clock())
    assert b.state == "WANDER"


def test_stop_freezes_transitions(qapp):
    b, sp, clock = make()
    b.stop(); b.force_wander_chance(1.0)
    clock.adv(seconds=9999); b.tick(clock())
    assert b.state == "IDLE"


def test_stroll_is_a_sustained_module_state(qapp):
    """散步是持续（`once=False`）的模块级状态：待机随机动作不能把它抢回 idle。"""
    b, sp, clock = make()
    assert b.request("stroll", PRIORITY_MODULE, once=False) is True
    assert b.state == "STROLL"
    b.force_wander_chance(1.0)
    clock.adv(seconds=9999); b.tick(clock())
    assert b.state == "STROLL"


def test_stroll_finished_returns_to_idle(qapp):
    b, sp, _ = make()
    b.request("stroll", PRIORITY_MODULE, once=False)
    b.on_stroll_finished()
    assert b.state == "IDLE" and sp.played[-1] == "idle"


def test_stroll_finished_ignored_when_other_state_took_over(qapp):
    """被拖拽抢走后，散步的收尾回调不该把状态从别处拽回待机。"""
    b, sp, _ = make()
    b.request("stroll", PRIORITY_MODULE, once=False)
    b.on_drag_started()
    b.on_stroll_finished()
    assert b.state == "DRAGGED"
