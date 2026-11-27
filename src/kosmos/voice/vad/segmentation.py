"""Deterministic speech segmentation over validated VAD probabilities."""

from enum import StrEnum

from kosmos.voice.audio.models import AudioChunk
from kosmos.voice.exceptions import InvalidSpeechSegmentError
from kosmos.voice.vad.config import VADSettings
from kosmos.voice.vad.framing import VAD_AUDIO_FORMAT
from kosmos.voice.vad.models import (
    AudioWindow,
    SegmentationResult,
    SpeechEvent,
    SpeechEventType,
    Utterance,
    UtteranceEndReason,
    VoiceActivityResult,
)


class SegmentationState(StrEnum):
    IDLE = "idle"
    POSSIBLE_SPEECH = "possible_speech"
    SPEECH_ACTIVE = "speech_active"
    POSSIBLE_END = "possible_end"


class DeterministicSpeechSegmenter:
    """Interpret ordered probabilities without wall-clock timing or backend knowledge."""

    def __init__(self, settings: VADSettings) -> None:
        self._settings = settings
        self._state = SegmentationState.IDLE
        self._expected_frame = 0
        self._pre_roll = bytearray()
        self._pre_roll_start = 0
        self._audio = bytearray()
        self._audio_start = 0
        self._speech_start: int | None = None
        self._candidate_speech_frames = 0
        self._possible_end: int | None = None
        self._silence_frames = 0
        self._utterance_id = 0
        self._active_id: int | None = None

    @property
    def state(self) -> SegmentationState:
        return self._state

    def accept(self, window: AudioWindow, activity: VoiceActivityResult) -> SegmentationResult:
        if window.start_frame != self._expected_frame:
            raise InvalidSpeechSegmentError(
                "Segmentation timeline is discontinuous; reset required"
            )
        if activity.start_frame != window.start_frame:
            raise InvalidSpeechSegmentError("Activity result does not match the audio window")
        if activity.audio_frame_count != window.audio.frame_count:
            raise InvalidSpeechSegmentError("Activity result frame count does not match audio")
        self._expected_frame = window.end_frame

        events: list[SpeechEvent] = []
        utterances: list[Utterance] = []
        probability = activity.probability
        high = probability >= self._settings.speech_threshold
        low = probability <= self._settings.end_speech_threshold

        if self._state is SegmentationState.IDLE:
            if high:
                self._start_candidate(window)
                self._confirm_if_ready(events)
            else:
                self._append_pre_roll(window.audio.data, window.start_frame)
            return SegmentationResult(tuple(events), ())

        self._audio.extend(window.audio.data)
        if self._state is SegmentationState.POSSIBLE_SPEECH:
            if not high:
                self._append_pre_roll(bytes(self._audio), self._audio_start)
                self._clear_active()
                return SegmentationResult()
            self._candidate_speech_frames += window.audio.frame_count
            self._confirm_if_ready(events)
        elif self._state is SegmentationState.SPEECH_ACTIVE and low:
            self._state = SegmentationState.POSSIBLE_END
            self._possible_end = window.start_frame
            self._silence_frames = window.audio.frame_count
        elif self._state is SegmentationState.POSSIBLE_END:
            if high:
                self._state = SegmentationState.SPEECH_ACTIVE
                self._possible_end = None
                self._silence_frames = 0
            elif low and self._possible_end is not None:
                self._silence_frames += window.audio.frame_count
                if self._silence_frames >= self._settings.min_silence_frames:
                    kept_end = min(
                        self._possible_end + self._settings.post_roll_frames,
                        self._audio_start + self._audio_frames,
                    )
                    result = self._complete(
                        kept_end, self._possible_end, UtteranceEndReason.SILENCE
                    )
                    events.extend(result.events)
                    utterances.extend(result.utterances)

        active = self._state in {
            SegmentationState.SPEECH_ACTIVE,
            SegmentationState.POSSIBLE_END,
        }
        if active and self._audio_frames >= self._settings.max_utterance_frames:
            end = self._audio_start + self._settings.max_utterance_frames
            result = self._complete(end, end, UtteranceEndReason.MAX_DURATION)
            events.extend(result.events)
            utterances.extend(result.utterances)

        return SegmentationResult(tuple(events), tuple(utterances))

    def finish(self) -> SegmentationResult:
        if self._state is SegmentationState.POSSIBLE_SPEECH:
            event = self._discard_event(UtteranceEndReason.STREAM_ENDED)
            self._reset_sequence()
            return SegmentationResult((event,), ())
        if self._state in {SegmentationState.SPEECH_ACTIVE, SegmentationState.POSSIBLE_END}:
            end = self._audio_start + self._audio_frames
            speech_end = self._possible_end if self._possible_end is not None else end
            return self._complete(end, speech_end, UtteranceEndReason.STREAM_ENDED)

        self._pre_roll.clear()
        return SegmentationResult()

    def discard(self) -> SegmentationResult:
        if self._state is SegmentationState.IDLE:
            self.reset()
            return SegmentationResult()
        event = self._discard_event(UtteranceEndReason.CANCELLED)
        self.reset()
        return SegmentationResult((event,), ())

    def reset(self) -> None:
        self._state = SegmentationState.IDLE
        self._expected_frame = 0
        self._pre_roll.clear()
        self._pre_roll_start = 0
        self._clear_active()

    @property
    def _audio_frames(self) -> int:
        return len(self._audio) // VAD_AUDIO_FORMAT.bytes_per_frame

    def _start_candidate(self, window: AudioWindow) -> None:
        self._state = SegmentationState.POSSIBLE_SPEECH
        self._audio_start = self._pre_roll_start if self._pre_roll else window.start_frame
        self._audio = self._pre_roll + bytearray(window.audio.data)
        self._pre_roll.clear()
        self._speech_start = window.start_frame
        self._candidate_speech_frames = window.audio.frame_count

    def _confirm_if_ready(self, events: list[SpeechEvent]) -> None:
        if self._candidate_speech_frames < self._settings.min_speech_frames:
            return
        assert self._speech_start is not None
        self._utterance_id += 1
        self._active_id = self._utterance_id
        self._state = SegmentationState.SPEECH_ACTIVE
        events.append(
            SpeechEvent(SpeechEventType.SPEECH_STARTED, self._speech_start, self._active_id)
        )

    def _complete(
        self,
        end_frame: int,
        speech_end_frame: int,
        reason: UtteranceEndReason,
    ) -> SegmentationResult:
        if self._active_id is None or self._speech_start is None:
            raise InvalidSpeechSegmentError("Cannot complete an unconfirmed utterance")
        available_end = self._audio_start + self._audio_frames
        if not self._audio_start < end_frame <= available_end:
            raise InvalidSpeechSegmentError("Utterance boundary exceeds buffered audio")
        byte_count = (end_frame - self._audio_start) * VAD_AUDIO_FORMAT.bytes_per_frame
        utterance_data = bytes(self._audio[:byte_count])
        remainder = bytes(self._audio[byte_count:])
        identifier = self._active_id
        utterance = Utterance(
            identifier=identifier,
            audio=AudioChunk(utterance_data, VAD_AUDIO_FORMAT),
            start_frame=self._audio_start,
            end_frame=end_frame,
            speech_start_frame=self._speech_start,
            speech_end_frame=min(max(speech_end_frame, self._speech_start), end_frame),
            end_reason=reason,
        )
        events = (
            SpeechEvent(
                SpeechEventType.SPEECH_ENDED, utterance.speech_end_frame, identifier, reason
            ),
            SpeechEvent(SpeechEventType.UTTERANCE_COMPLETED, end_frame, identifier, reason),
        )
        self._reset_sequence()
        if remainder:
            self._append_pre_roll(remainder, end_frame)
        return SegmentationResult(events, (utterance,))

    def _append_pre_roll(self, data: bytes, start_frame: int) -> None:
        if not data or self._settings.pre_roll_frames == 0:
            self._pre_roll.clear()
            self._pre_roll_start = start_frame + len(data) // VAD_AUDIO_FORMAT.bytes_per_frame
            return
        if not self._pre_roll:
            self._pre_roll_start = start_frame
        self._pre_roll.extend(data)
        maximum = self._settings.pre_roll_frames * VAD_AUDIO_FORMAT.bytes_per_frame
        excess = len(self._pre_roll) - maximum
        if excess > 0:
            del self._pre_roll[:excess]
            self._pre_roll_start += excess // VAD_AUDIO_FORMAT.bytes_per_frame

    def _discard_event(self, reason: UtteranceEndReason) -> SpeechEvent:
        frame = self._audio_start + self._audio_frames
        return SpeechEvent(
            SpeechEventType.UTTERANCE_DISCARDED,
            frame,
            self._active_id,
            reason,
        )

    def _clear_active(self) -> None:
        self._audio.clear()
        self._audio_start = 0
        self._speech_start = None
        self._candidate_speech_frames = 0
        self._possible_end = None
        self._silence_frames = 0
        self._active_id = None
        self._state = SegmentationState.IDLE

    def _reset_sequence(self) -> None:
        self._pre_roll.clear()
        self._pre_roll_start = self._expected_frame
        self._clear_active()
