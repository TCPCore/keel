# Demo video description

One minute fifty-five seconds, ten annotated scenes, narrated and captioned. It walks
from the gap to a verified card and ends on the cost. Every number in it is produced by
this repository.

Watch: https://tomscot-keel.hf.space/video (embedded) or
https://youtu.be/FvseA22YEDo (YouTube).

## What the video shows

| time | scene | what happens |
|---|---|---|
| 0:00 | The gap | The hero sentence: Meta checks the base before release and the conversation at runtime, and nothing checks the derivative artifact after release. |
| 0:12 | Built in the open | A real terminal: `keel selftest`, a scan that catches a format collapse, and a policy that blocks a card with no harmful half. The refusal is the product. |
| 0:27 | The run | A 30B open checkpoint answering 32 harmful requests, timestamped 12:28:05 to 12:39:38, ending at 29 of 32 compliant. |
| 0:42 | The families | One table across four families. Packaging variants stay at zero harmful compliance, behavioural edits move to 0.19, 0.75, 0.78, 0.81 and 0.91. |
| 1:00 | The cards | Cards grouped by model, each carrying a fingerprint. |
| 1:10 | A card | Drift axes, validity, harmful compliance and the limits of the scan, read in one minute. |
| 1:21 | Verify | The card recomputed from the committed responses. MATCH means reproduced, not screenshotted. |
| 1:29 | Tamper | One axis moved by 0.25 changes the fingerprint, and verification then fails. |
| 1:36 | Reproduce | The probes, the responses, the verifier, the link checker and the stress suite, all runnable from the repo. |
| 1:46 | Close | Two dollars, twenty minutes, one card. |

## Narration, in one sentence per scene

1. The gap is the derivative artifact.
2. The build is four commands, and one of them refuses.
3. The run is real, timestamped, and costs about two dollars.
4. The effect reproduces across families, including edits we did not make.
5. Every checkpoint gets one card.
6. The card answers what moved, whether it was valid, and how often it complied.
7. Verify recomputes instead of trusting.
8. Tampering changes the fingerprint, and the check rejects it.
9. A stranger can rerun all of it.
10. Two dollars, twenty minutes, one card.

## Captions

The subtitle file is `video/captions.srt`, served at
https://tomscot-keel.hf.space/demo.srt. The video is generated, not hand-edited: the
scenes, narration and captions are built by `python video/build.py` from screenshots of
the live site and the recorded 30B log.
