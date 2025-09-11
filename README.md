# Cutie Labeling Assist Panel (Add-On)

<img width="2006" height="867" alt="image" src="https://github.com/user-attachments/assets/6c349ede-00a4-4b34-a04f-06373ab58e95" />


This add-on injects a Labeling Assist Panel into the Cutie UI so you can proofread and quickly fix labeling after an initial propagation pass. By pasting a short snippet at the end of __init__, the panel appears as an additional tool docked to the Cutie interface.

**Where to paste**: Cutie/gui/main_controller.py — around line 128 (the last line of __init__).
Line numbers can vary by version; the key is to place the snippet at the very end of the constructor.

## When to Use

- You already have a Cutie pretrained or finetuned model whose errors are rare except in heavy occlusion regions.

- Your workflow is to propagate all frames first, then review problem spots afterward.

- You want utilities like:

  - Single-frame propagation (stepwise),

  - Selective re-propagation over risky segments,

  - Batch ID reassignment (switch IDs over a chosen range).


## Integration

1. Copy the snippet from this repository.

2. Open Cutie/gui/main_controller.py.

3. Paste the snippet at the end of __init__ (around line 128 in most builds).

4. Run Cutie. You’ll see a new button at the bottom-right to open the Assist Panel.

## What You Can Do

- Selective Play : Review only frames where mask-based inter-animal distance is below a margin threshold, plus frames within post_window after those hits.

- Selective Re-Propagation : Using the same occlusion-risk detection as above, re-propagate only from the current region up to the next risky region. This keeps fixes tight and fast.

- Single-Frame Propagation : Step one frame at a time to inspect and correct fine-grained issues.

- ID Reassign : Bulk-change IDs (colors) across a selected frame range—handy for quick ID switches after crossings.

## Notes & Caveats

The Assist Panel plays nicely with core Cutie features (memory init, ID changes, interaction-based ID edits, frame navigation).

However, Cutie’s built-in play/propagation and the Assist Panel’s play/propagation can conflict if used simultaneously. Avoid running both at the same time.

Visualization from the main Cutie UI still applies during Assist Panel playback,
but does not apply when sampling is enabled (sampling is for quick screening).

## Typical Workflow

1. Run your standard full propagation (without manual supervision)

2. Open Assist Panel → Selective Play to jump through likely occlusions only.

3. For segments that need fixes, use Selective Re-Propagation or Single-Frame Propagation.

4. If identities crossed, use ID Reassign over the affected range.

## Requirements

1. A working Cutie setup.

2. A pretrained or finetuned Cutie model.

3. Videos where errors are predominantly tied to occlusion events.

## Status

Experimental. Feedback and issue reports are very welcome.
