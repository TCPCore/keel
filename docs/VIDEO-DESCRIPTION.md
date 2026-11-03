# Demo video description

Two minutes, eight recorded chapters, narrated and captioned. It is a live run of the
deployed Space: real clicks on the real pages, not screenshots. Every number in it is
produced by this repository.

Watch: https://tomscot-keel.hf.space/video (embedded, 1080p original), or the 1440p
mirror on YouTube: https://www.youtube.com/watch?v=EP5-Xh9t1GY.

## What the video shows

| time | chapter | what happens |
|---|---|---|
| 0:00 | Open | The live fleet: twelve checkpoints, each with a verdict, a validity state and a fingerprint. |
| 0:07 | Verify | Click Verify. The server recomputes the card from the committed responses, and it matches. |
| 0:13 | Tamper | One number changed, the fingerprint moves, verification fails. |
| 0:19 | Families | The same ablation under one frozen judge: Qwen 0.97, Mistral 0.81, Glimmer 0.16. |
| 0:35 | Scan | Upload your own response files and get a card. |
| 0:39 | Close | One card, about two dollars. |

## Narration

1. This is the live product. Twelve checkpoints, each with a verdict, a validity state and a fingerprint.
2. Click Verify. The server recomputes the card from the committed responses. It matches.
3. Tamper with one number. The fingerprint changes, and verification fails.
4. The same ablation, one frozen judge: Qwen zero point nine seven, Mistral zero point eight one, Glimmer zero point one six. Refusal is concentrated in Qwen and Mistral, and distributed in Glimmer.
5. Scan your own. Upload the response files and get a card.
6. One card, about two dollars.

## Captions

The subtitle file is `video/captions.srt`, served at
https://tomscot-keel.hf.space/demo.srt. The video is generated, not hand-edited: the six
chapters are recorded by `scripts/record_live_demo.py` and dubbed with
`scripts/build_live_video.py`, which burns a lower-third title on each chapter.
