# Official Base-mode contract (distilled)

Apply only to T2VA, I2VA, L2VA, and FL2VA. Output exactly the three fields named below, in this order. Never add Ref2VA sections.

```text
integrated_multimodal_description:
overall_soundscape:
non_diegetic_music:
```

- T2VA has no alignment preamble.
- I2VA adds exactly: `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`
- FL2VA adds exactly: `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.` Replace N and S.SS with the real final shot and exact duration.
- L2VA adds exactly: `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.`
- Start with `[Shot 1]` without a timestamp. Only later cuts use `[Shot N] At MM:SS.mmm, ...`; timestamps strictly increase and remain inside the requested duration.
- FL2VA should normally be one continuous shot. Describe a physically plausible path from the first-frame state to the exact final-frame state.
- Camera movement is natural prose specifying type, amplitude, and speed only when meaningful.
- Assign `(S1)`, `(S2)` only to actual vocal sources, in first-speaking order. Exact spoken words alone go inside `<d>[Language] ...</d>`.
- Put synchronized dialogue, diegetic music, and event sounds in the timeline. `overall_soundscape` contains ambience, Foley/contact, and nonverbal human sound without repeating dialogue. `non_diegetic_music` describes instrumentation, tempo, rhythm, and dynamics, or `N/A`.

Integrated example (structure, not reusable content):

```text
integrated_multimodal_description: [Shot 1] 一名女子站在雨棚边缘，先听见身后金属落地声，肩膀骤然收紧，视线向右后方移动。镜头以缓慢小幅推近响应她的回头动作；她转身半步、确认空无一人后缓慢呼气，最终背靠立柱站稳。(S1) 她压低声音说道：<d>[Chinese] 谁在那里？</d>

overall_soundscape: 密集雨声持续敲击铁皮雨棚，远处雷声低沉滚过，金属零件落地后弹跳两次，她回头时衣料轻擦并有一次短促吸气。

non_diegetic_music: 低音大提琴维持稀疏长音，极慢速度，音量在金属声后轻微上升并于结尾收弱。
```
