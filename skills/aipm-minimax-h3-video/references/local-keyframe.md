# Local Add Guide multi-keyframe contract

This is AIPM/CineTimeline `h3_keyframe`, not official FL2VA's two-image preamble. The runtime injects images using Add Guide and supplies the actual `keyframe_bindings.local_frame` positions.

Use exactly three fields, in order:
```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

Describe every assigned frame and adjacent interval: starting state, continuous observable change, next state. Use the supplied numbers as `第N帧` or `frame N`, not a guessed duration×24 inclusive final frame. First image is frame 0; use the actual final binding. No `<Picture N>`, `<Subject N>`, `<Video N>` or `<Audio N>` labels and no official first/last alignment preamble. Name concrete actors/objects and numbered keyframe images instead.

Normally preserve continuous action when images depict one event; preserve an approved cut when they intentionally change viewpoint/time. Do not invent a morph to join incompatible states. Preserve requested medium and intentional costume/light changes. Frame instructions are target alignment, not a guarantee of exact generated pixels or action at that frame.

Several frame bindings within a continuous event still belong to one `[Shot]`; a new bound image is not itself a cut. At an approved cut, preserve the relevant pre-cut action phase, contact/ownership and direction in the post-cut opening, or preserve the explicitly approved discontinuity. Do not invent intermediate actions to hide incompatible bindings; surface that conflict during planning.
