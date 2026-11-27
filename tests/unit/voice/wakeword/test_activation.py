from kosmos.voice.wakeword.activation import WakeWordActivationPolicy
from kosmos.voice.wakeword.config import WakeWordSettings
from kosmos.voice.wakeword.models import WakeWordActivationState, WakeWordResult


def _result(score: float, index: int, *, ready: bool = True) -> WakeWordResult:
    start = index * 1_280
    return WakeWordResult(score, start, start + 1_280, 0.0, ready)


def test_policy_requires_consecutive_confirmation_frames() -> None:
    policy = WakeWordActivationPolicy(WakeWordSettings())

    assert policy.accept(_result(0.5, 0)) is None
    assert policy.state is WakeWordActivationState.POSSIBLE_ACTIVATION
    detection = policy.accept(_result(0.8, 1))

    assert detection is not None
    assert detection.detection_frame == 2_560
    assert policy.state is WakeWordActivationState.COOLDOWN


def test_low_score_cancels_candidate_and_warmup_never_activates() -> None:
    policy = WakeWordActivationPolicy(WakeWordSettings())

    policy.accept(_result(0.9, 0, ready=False))
    policy.accept(_result(0.9, 1))
    assert policy.accept(_result(0.1, 2)) is None
    assert policy.accept(_result(0.9, 3)) is None


def test_cooldown_uses_audio_frames_and_requires_low_score_rearm() -> None:
    settings = WakeWordSettings(confirmation_frames=1, cooldown_seconds=0.08)
    policy = WakeWordActivationPolicy(settings)

    assert policy.accept(_result(0.9, 0)) is not None
    assert policy.accept(_result(0.9, 1)) is None
    assert policy.accept(_result(0.9, 2)) is None
    assert policy.state is WakeWordActivationState.REARM
    assert policy.accept(_result(0.2, 3)) is None
    assert policy.state is WakeWordActivationState.ARMED
    assert policy.accept(_result(0.9, 4)) is not None
    assert policy.suppressed_detection_count == 2


def test_discontinuity_resets_confirmation_state() -> None:
    policy = WakeWordActivationPolicy(WakeWordSettings())
    policy.accept(_result(0.9, 0))
    discontinuous = WakeWordResult(0.9, 5_000, 6_280, 0.0, True)

    assert policy.accept(discontinuous) is None
    assert policy.state is WakeWordActivationState.POSSIBLE_ACTIVATION
