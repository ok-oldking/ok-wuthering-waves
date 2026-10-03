"""Bounded visual-state rotation, independent of input/capture and chain count."""


class YangYangSpPolicy:
    FIELD_TIMEOUT = 20.0
    HOLD_TIMEOUT = 8.0
    NORMAL_SETTLE = 0.35
    READY_SETTLE = 0.12
    E_RESPONSE_TIMEOUT = 0.9

    def __init__(self):
        self.hold_started = None
        self.normal_since = None
        self.heavy_ends = 0
        self.heavy_blocked = False
        self.r_used = False
        self.q_used = False
        self.pending_e = None
        self.e_attempts = 0
        self.e_form = ''
        self.signature = None
        self.stable_since = 0.0
        self.reason = ''
        self.feedback = ''

    def choose(self, state, elapsed, *, can_r=True, can_q=False, con_full=False):
        self.feedback = ''
        if state.signature != self.signature:
            self.signature = state.signature
            self.stable_since = elapsed
        stable = elapsed - self.stable_since >= self.READY_SETTLE

        if self.pending_e is not None:
            sent_form, sent_at = self.pending_e
            if stable and state.attack != 'unknown' and state.enhanced_e != sent_form:
                self.feedback = 'E_ICON_CHANGED (visual response, not proof of damage)'
                self.pending_e = None
                self.e_attempts = 0
            elif elapsed - sent_at >= self.E_RESPONSE_TIMEOUT:
                self.feedback = 'E_NO_VISUAL_RESPONSE'
                self.pending_e = None

        if self.hold_started is not None:
            if elapsed - self.hold_started >= self.HOLD_TIMEOUT:
                self.hold_started = None
                self.normal_since = None
                self.heavy_blocked = True
                self.reason = 'heavy_timeout_unconfirmed'
                return 'release'
            if state.normal:
                if self.normal_since is None:
                    self.normal_since = elapsed
                if elapsed - self.normal_since >= self.NORMAL_SETTLE:
                    self.hold_started = None
                    self.normal_since = None
                    self.heavy_ends += 1
                    self.reason = 'normal_icon_returned_stably'
                    return 'release'
            else:
                # Unknown frames and depleted resources do not end the combo.
                self.normal_since = None
            self.reason = 'protect_heavy_or_followup'
            return 'hold'

        if elapsed >= self.FIELD_TIMEOUT:
            self.reason = 'field_timeout'
            return 'switch'
        if stable and state.normal:
            self.heavy_blocked = False
        if (state.heavy_ready or state.followup) and not self.heavy_blocked:
            if not stable:
                self.reason = 'confirm_heavy_icon'
                return 'wait'
            self.hold_started = elapsed
            self.normal_since = None
            self.reason = 'resume_followup' if state.followup else 'heavy_ready'
            return 'hold'

        if self.pending_e is not None:
            self.reason = 'await_E_visual_response'
            return 'wait'
        if stable and state.enhanced_e != self.e_form:
            self.e_form = state.enhanced_e
            self.e_attempts = 0
        if stable and state.enhanced_e and self.e_attempts < 2:
            self.e_form = state.enhanced_e
            self.e_attempts += 1
            self.pending_e = (state.enhanced_e, elapsed)
            self.reason = 'enhanced_E_ready'
            return 'E'
        if stable and state.liberation_ready and can_r and not self.r_used:
            self.r_used = True
            self.reason = 'liberation_ready'
            return 'R'
        if state.normal and (self.heavy_ends >= 2 or (self.heavy_ends >= 1 and con_full)):
            self.reason = 'rotation_finished'
            return 'switch'
        if stable and state.normal and can_q and not self.q_used:
            self.q_used = True
            self.reason = 'echo_safe_window'
            return 'Q'
        self.reason = 'normal_attack_build_resource'
        return 'normal'
