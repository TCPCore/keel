# The demo video

Three minutes. It sells one idea: **this is the tool that refuses to lie**, and it proves
it with a fingerprint you can recompute.

Do not tour the architecture. The ledger, the webhook and the policy engine are appendix
material. The video shows four things and one live run.

## What sells it

1. **A number with a control.** Base 0.00 harmful compliance, ablated 0.81, quantized
   0.00. Same panel, same judge, two dollars.
2. **A refusal.** M2's card says `MEASUREMENT SUSPECT` because the model answered
   everything with code. Five axes would have said "no drift". The gate said no.
3. **A proof.** Verify recomputes the card and returns `MATCH`. Tamper edits one number
   and the fingerprint changes. That is the difference between a dashboard and an audit.
4. **A live 30B run.** Timestamps from the job, then the card. Not a screenshot.

## Shot list

| time | shot | voiceover |
|---|---|---|
| 0:00 | Terminal, repo root | "Open weights are the strategy. The risk is what happens after release." |
| 0:08 | The Space hero, then the fleet table | "One scanner, ten checkpoints, one card. Five frontier baselines, and four derivatives we built or found." |
| 0:25 | Hover the base row, then candidate A | "Same 32 probes, same judge. The base refuses everything. The ablated checkpoint complies with 26 of 32." |
| 0:40 | Click M2's card | "This one is the interesting failure. Five axes saw no drift." |
| 0:48 | The `MEASUREMENT SUSPECT` banner | "Because it answered every probe with Python. The format gate marks the card invalid before the axes can lie." |
| 1:00 | Click Verify | "Verify recomputes the card from the committed responses." |
| 1:05 | The `MATCH` page, fingerprint visible | "Same fingerprint. This is not a screenshot; it is a recomputation." |
| 1:12 | Click Tamper test | "Change one number by a quarter of a point, and the fingerprint changes." |
| 1:20 | Back to the fleet, click Re-score on A | "Re-score runs the judge live, on the same responses, in about fifteen seconds." |
| 1:35 | Cut to the 30B run log with timestamps | "And the 30B generation is real. Here is the job from this morning." |
| 1:42 | Log lines scrolling: `[HH:MM:SS] 12/32 ...` | "Glimmer 30B, ablated at layer 24, generating live. Twenty-two minutes, timestamps on every probe." |
| 2:10 | The new card appearing | "Twenty-six of thirty-two. The card is produced by the same pipeline as the ones on the site." |
| 2:20 | Scan your own: drop a JSONL, card returns | "Anyone can do this to their own checkpoint. Download the probes, upload responses, get a card in a second." |
| 2:40 | Access page, manifest | "The harmful completions are not published. Reviewers request them, and the hashes in the manifest prove what they receive." |
| 2:50 | Cost card / closing frame | "Two dollars a scan. No green without the harmful half. The tool refuses to certify what it cannot measure." |

## The b-roll to capture

Run this before recording, keep the log, and cut it into 1:35:

```console
$ modal run scripts/modal_generate.py --stage m1 --suite harmful | tee video-m1.log
```

The log prints `[HH:MM:SS] n/32 probe chars` per probe, which is what makes the run
credible. Show the first line and the last line close together with the timestamps
visible, then the generated card.

## What not to show

- The ledger, the webhook, `keel batch`, the policy JSON. They are real and they are not
  the pitch.
- A dark-screen terminal tour. The Space is light for a reason.
- Any claim that the 30B generation is instant. Say "twenty-two minutes" out loud; it
  makes the two dollars credible.

## Recording the screen on a Mac

macOS has a built-in recorder: **Shift + Command + 5**, then "Record Selected Portion".
Record the browser at 1440x900 with the cursor visible. For the terminal segments, use
`script`, which is the only recorder installed here:

```console
$ script -q demo.typescript bash -c 'keel selftest; keel scan ...'
$ cat -v demo.typescript
```

A captured session is at `/tmp/keel-demo.typescript` from this session: selftest, a scan
of M0 against M2, the policy decision, and the repro verifier. It can be replayed in the
video as terminal b-roll.

## The fresh 30B run for the video

Run on 28 October, timestamps printed per probe in
`.tools/runs/video-m1.log`:

```
first probe  [12:28:05]
last probe   [12:39:38]
result       29 of 32 compliant, 0.906, 95% CI [0.81, 1.00]
```

That is 11 minutes 33 seconds of generation after the model load, which is what makes the
"twenty minutes a scan" claim credible. Show the first and last timestamps in the same
frame, then the judged result.

## Recording notes

- 1440x900 browser, zoom at 110 percent, cursor visible, no browser chrome.
- Record in one take per section, cut on the beat, no music.
- Have the Verify result open in a tab already so there is no dead air.
- If a click fails, keep the failure and say why: a tool that shows its own bad
  measurement is the product.

## What a judge should remember after the video

1. A base model at 0.00 and an ablated model at 0.81, with a quantization control at 0.00.
2. A card that said "suspect" when the axes said nothing.
3. A fingerprint that changed when one number changed.
4. A live 30B run with timestamps.
5. Two dollars.

## The produced video

`video/keel-demo.mp4` is built, not shot: 115 seconds, 1600x900, ten annotated scenes with
narration and burned captions. It walks the gap, the recorded 30B run, the four-family
table, the cards, verify, tamper, the guide and the close.

- `video/captions.srt` is the same caption track as a subtitle file.
- `video/shots/` holds the source screenshots, captured from the live Space.
- `video/build.py` regenerates everything from those shots.

Rebuild:

```console
$ python video/build.py
```

It needs Chrome (for the annotated slides), `say` and `afconvert` (for the narration), and
an ffmpeg binary. The build sets `Samantha` at 160 words per minute and pads each scene by
0.9 seconds.

The narration is machine speech, not a human recording. It is honest, clear and
replaceable: edit the `SCENES` list in `video/build.py` and rebuild to change any line.

## What the video argues, in order

1. The gap: the derivative artifact is the one point nothing checks.
2. Built in the open: selftest, scan, policy, and a policy that blocks a card with no
   harmful half.
3. The run: 32 probes, 29 answered, 11 minutes, two dollars.
4. The families: only behavioural edits move compliance.
5. The cards: one card per checkpoint, fingerprinted.
6. A card: drift, validity, compliance.
7. Verify: recomputed, not stored.
8. Tamper: one number, a new fingerprint.
9. Reproduce: probes, responses, verifier, stress suite.
10. Close: two dollars, twenty minutes, one card.
