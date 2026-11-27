# Wake Word Model Training Strategy

This guide separates confirmed runtime requirements from a proposed future training procedure. No
Kosmos classifier has been trained, approved, downloaded, or incorporated into the repository.
Training dependencies must remain outside the Kosmos runtime environment.

## Confirmed constraints

- Target phrase: institutional spelling `Kosmos`, natural Brazilian Portuguese pronunciation of
  the Portuguese word "cosmos".
- Runtime classifier format: a binary ONNX model compatible with the auxiliary feature models and
  the tensor contract documented in the wake-word architecture specification.
- Audio reference: mono 16 kHz PCM. Training must preserve the preprocessing distribution used by
  the selected feature models.
- Runtime is local-only and CPU-only. Training may use separate hardware, but local data must not
  be sent externally without explicit authorization.
- Real recordings, generated speech, background data, room responses, pretrained features, and
  every model require provenance, consent, license, and redistribution review.
- The provisional Razo voice is blocked as a synthetic source until its dataset and voice-rights
  provenance are resolved.

## Proposed procedure (not executed)

1. Freeze one upstream training revision and reproduce its environment separately from Kosmos.
2. Approve Brazilian Portuguese TTS sources and/or consented speakers representing pronunciation,
   speaking rate, distance, pitch, microphones, and acoustic conditions.
3. Define hard negatives for Portuguese words and phrases that are acoustically close to Kosmos,
   plus television, music, assistant playback, conversation, and development-environment noise.
4. Split speakers and acoustic sources before augmentation so training, validation, and evaluation
   cannot share a speaker or source recording.
5. Generate or record positives only after privacy and rights approval. Never commit recordings,
   personal metadata, generated clips, datasets, or local model files.
6. Train the classifier against the exact reviewed feature pipeline, export ONNX, and record model
   input/output metadata, revision, configuration, sources, licenses, and SHA-256.
7. Compare scores and embeddings against the pinned reference backend using controlled audio before
   promoting the direct adapter as equivalent.
8. Evaluate false acceptance, false rejection, detection timing, continuous high scores,
   self-triggering, CPU, memory, and real-time factor on held-out data.
9. Calibrate threshold, confirmation, cooldown, and rearm from the evaluation set rather than the
   training or validation sets.
10. Perform authorized physical Windows and Ubuntu offline validation before any production claim.

The openWakeWord example suggests large synthetic datasets, but its English-oriented generation
workflow is not evidence of Brazilian Portuguese quality. Dataset size, class balance, augmentation,
and acceptance targets remain proposals until an approved experiment plan exists.

## Artifact record required for promotion

Record the classifier name and identifier, source repository and immutable revision, training-code
license, target phrase and locale, dataset inventory and rights, TTS sources, auxiliary feature
model identities, preprocessing, tensor names/types/shapes, evaluation split, measured results,
known limitations, file size, and locally calculated SHA-256. Record auxiliary artifacts
independently; a classifier manifest cannot license or verify them by implication.

## Current blockers

- no approved Kosmos training dataset;
- no approved Brazilian Portuguese synthetic-voice source;
- unresolved exact provenance and redistribution terms for auxiliary feature model files;
- no trained Kosmos classifier artifact;
- no reference-equivalence run with real models;
- no real positive/negative evaluation corpus;
- no threshold calibration or physical cross-platform validation.

Until these blockers are resolved, the correct status is: infrastructure and backend code
implemented; custom model unavailable; training, real detection, offline behavior, performance,
quality, and production readiness pending.
