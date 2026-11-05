"""H3 prompt compilation checks; no inference or media processing."""
import re
from pathlib import Path

VERSION = '2026-11-01.3'
FIELDS = r'subject_definitions|summary|retention_analysis|detailed_description|integrated_multimodal_description|overall_soundscape|non_diegetic_music'
BASE = ['integrated_multimodal_description', 'overall_soundscape', 'non_diegetic_music']
REF = ['subject_definitions', 'summary', 'retention_analysis', 'detailed_description', 'overall_soundscape', 'non_diegetic_music']
DIALOGUE = re.compile(r'<d>\s*\[([^\]\n]+)\]\s*(.*?)</d>', re.S)
MEDIA = re.compile(r'<(Picture|Video|Audio)\s+(\d+)>', re.I)

class ContractError(ValueError):
    pass

def sections(text):
    matches = list(re.finditer(rf'(?m)^({FIELDS})\s*:', text))
    return [(m.group(1), text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()) for i,m in enumerate(matches)]

def clock(value):
    minute, second = value.split(':')
    if float(second) >= 60:
        raise ContractError('镜头时间的秒数必须小于60')
    return int(minute)*60+float(second)

def validate_structure(text, mode, duration):
    parts = sections(text)
    if [name for name,_ in parts] != (REF if mode == 'h3_ref2va' else BASE):
        raise ContractError('H3字段或顺序错误；必须只使用当前模式的三段或六段结构')
    if any(not content for _,content in parts):
        raise ContractError('H3段落不能为空；无配乐写N/A')
    if '【' in text or '】' in text or '```' in text:
        raise ContractError('H3机器提示词不能包含编辑标题或Markdown代码围栏')
    if text.count('<d>') != text.count('</d>') or text.count('<d>') != len(DIALOGUE.findall(text)):
        raise ContractError('台词必须使用完整的<d>[语言]逐字文本</d>')
    # Catch the observed raw-quoted speaker output without making editorial
    # dialogue differences or nonverbal performance into new content gates.
    untagged = DIALOGUE.sub('', text)
    if re.search(r'\(S\d+(?:\s*,\s*S\d+)*\)\s*[:：]?\s*["“]', untagged):
        raise ContractError('说话人后的直接台词缺少<d>[Language]原文</d>标签')
    if any(not words.strip() for _,words in DIALOGUE.findall(text)):
        raise ContractError('台词正文不能为空')
    body = dict(parts).get('detailed_description', dict(parts).get('integrated_multimodal_description',''))
    narrative = DIALOGUE.sub('', body)
    shots = list(re.finditer(r'\[Shot\s+(\d+)\]', narrative))
    if [int(s.group(1)) for s in shots] != list(range(1,len(shots)+1)) or not shots:
        raise ContractError('镜头编号必须从[Shot 1]开始连续递增')
    previous = 0.0
    for i,shot in enumerate(shots):
        tail = narrative[shot.end():shots[i+1].start() if i+1<len(shots) else len(narrative)]
        stamp = re.match(r'\s*At\s+(\d{2}:\d{2}(?:\.\d{1,3})?)',tail)
        if i == 0 and stamp:
            raise ContractError('[Shot 1]不带切镜时间')
        if i:
            if not stamp:
                raise ContractError('后续镜头必须以At MM:SS.mmm指定切镜时间')
            value = clock(stamp.group(1))
            if value <= previous or value < 0 or value > duration:
                raise ContractError('切镜时间必须严格递增且不超过片段时长')
            previous = value
    # Only target-timeline cues, not source-media offsets or spoken clock text.
    for stamp in re.finditer(r'(?:\bAt|\bat|\bby|\buntil|\baround|在|于|直到|约|至|到)\s*(\d{2}:\d{2}(?:\.\d{1,3})?)',narrative):
        if clock(stamp.group(1)) > duration:
            raise ContractError('动作或对白结束时间超出当前片段时长')
    if mode == 'h3_keyframe' and re.search(r'<(?:Picture|Subject|Video|Audio)\s+\d+>',text,re.I):
        raise ContractError('Add Guide关键帧模式使用帧号，不使用多模态媒体标签')

def normalized_words(text):
    return re.sub(r'[\W_]+', '', re.sub(r'<(?:scenetrans|cutoff)>','',text), flags=re.UNICODE)

def strict_dialogue_events(text, planned):
    """Match by exact planned words, allowing one line split into several blocks."""
    plans=[]
    for line in planned:
        pieces=re.split(r'[：:]',str(line),maxsplit=1)
        if len(pieces)!=2 or not all(piece.strip() for piece in pieces):
            raise ContractError('台词计划须包含角色名与逐字台词')
        plans.append((pieces[0].strip(),normalized_words(pieces[1])))
    matches=list(DIALOGUE.finditer(text))
    if not plans:
        return []
    events=[]; index=0; remainder=plans[0][1]
    for match in matches:
        spoken=normalized_words(match.group(2))
        if re.fullmatch(r'(?:嗯|哼|啊|哦|呃|唉|哈|呵|噢|喘息|呻吟|惊呼|笑声|轻哼)+', spoken):
            if index >= len(plans) or not remainder.startswith(spoken):
                continue
        if index>=len(plans) or not spoken or not remainder.startswith(spoken):
            raise ContractError('台词与计划不一致：检查漏句、增词、改写或顺序；须保留原文')
        role=plans[index][0]; events.append((match,role))
        remainder=remainder[len(spoken):].lstrip()
        if not remainder:
            index+=1
            if index<len(plans): remainder=plans[index][1]
    if index!=len(plans):
        raise ContractError('台词未完整写入H3正文；必须覆盖计划的每一句')
    return events

def content_warnings(text, planned):
    """Editorial differences never block generation or invent speaker identities."""
    warnings = []
    try:
        strict_dialogue_events(text, planned)
    except ContractError as exc:
        warnings.append("对白与计划存在差异，请复核：" + str(exc))
    cursor = 0
    for match in DIALOGUE.finditer(text):
        clause = re.split(r'[。！？\n]|<scenetrans>|<cutoff>', text[cursor:match.start()])[-1]
        groups = re.findall(r'\(S\d+(?:\s*,\s*S\d+)*\)', clause)
        audio_cue = bool(re.search(r'<Audio\s+\d+>', clause)) and not re.search(r'<Subject\s+\d+>', clause)
        if len(groups) != 1 and not (audio_cue and not groups):
            warnings.append("发声缺少唯一说话人编号组，请复核；未自动猜测角色。")
            break
        cursor = match.end()
    return list(dict.fromkeys(warnings))

def dialogue_events(text, planned):
    try:
        return strict_dialogue_events(text, planned)
    except ContractError:
        return []


def bind_dialogue(text, planned):
    events=dialogue_events(text,planned)
    if not events:
        return text
    role_ids={}
    for _,role in events:
        role_ids.setdefault(role,len(role_ids)+1)
    assigned_voices = bool(re.search(r"\(S\d+(?:\s*,\s*S\d+)*\)", text))
    output=[]; cursor=0
    for match,role in events:
        between=text[cursor:match.start()]
        # A pause or previous spoken block does not change who is speaking.
        boundaries=list(re.finditer(r'[。！？\n]|<scenetrans>|<cutoff>',between))
        boundary=boundaries[-1].end() if boundaries else 0
        head,clause=between[:boundary],between[boundary:]
        for other in role_ids:
            if other!=role and re.match(rf'\s*{re.escape(other)}\s*(?:\(S\d+\)\s*)?(?:说道|回答|说|says\b|replies\b)',clause):
                return text
        marker=f'(S{role_ids[role]})'
        groups = re.findall(r'\(S\d+(?:\s*,\s*S\d+)*\)', clause)
        if groups:
            # Collapse only redundant copies of the exact same solo marker.
            # Preserve compound groups and all distinct existing source assignments.
            if len(set(groups)) == 1 and ',' not in groups[0]:
                first = True
                def keep_first(match):
                    nonlocal first
                    if first:
                        first = False
                        return match.group(0)
                    return ''
                clause = re.sub(r'\(S\d+\)', keep_first, clause)
        elif not assigned_voices and not re.search(r'<Audio\s+\d+>', clause):
            clause += marker + ' '
        output.extend((head,clause,match.group(0)))
        cursor=match.end()
    output.append(text[cursor:])
    return ''.join(output)

def validate_segment(text, planned, active_references, mode):
    if planned and not DIALOGUE.search(text):
        raise ContractError('本段已有明确对白计划，却缺少实际台词标签；必须将每句原文写入<d>[Language]原文</d>，不能仅描述人物说话。')
    bound = bind_dialogue(text,planned)
    parts = dict(sections(bound))
    body = parts.get('detailed_description', parts.get('integrated_multimodal_description',bound))
    cursor=0
    for match in DIALOGUE.finditer(body):
        prefix=body[cursor:match.start()]
        clause=re.split(r'[。！？\n]|<scenetrans>|<cutoff>',prefix)[-1]
        if len(re.findall(r'\(S\d+\)',clause))!=1:
            pass  # Editorial warning only; preserve the generated performance.
        cursor=match.end()
    if mode != 'h3_ref2va':
        return
    canonical=lambda kind,index: f'<{kind.title()} {int(index)}>'
    active={canonical(*m) for ref in active_references for m in MEDIA.findall(str(ref))}
    if len(active)>12:
        raise ContractError('单段有效图/视频/音频素材合计不能超过12份')
    used={canonical(*m) for m in MEDIA.findall(text)}
    if used-active:
        raise ContractError('H3引用了当前片段未启用的素材：'+', '.join(sorted(used-active)))
    definitions=dict(sections(text)).get('subject_definitions','')
    defined=set(re.findall(r'(?m)^\s*(<Subject\s+\d+>)',definitions))
    subjects=set(re.findall(r'<Subject\s+\d+>',text))
    if subjects-defined:
        raise ContractError('H3使用了未定义的Subject标签：'+', '.join(sorted(subjects-defined))+'。请在本段 subject_definitions 中逐行定义实际使用的标签，并沿用已有身份和有效参考；无法绑定时移除该未定义引用。')
    retention=parts.get('retention_analysis','')
    for label in subjects | {item for item in used if item.startswith('<Audio ')}:
        if label not in retention:
            raise ContractError('保留分析遗漏了当前追踪项：'+label)
    if (subjects or used) and not re.search(r'\b(?:fully_preserved|partially_preserved|attribute_transfer|weak_reference|fully_copy|partially_copy|reference)\b',retention):
        raise ContractError('保留分析缺少合法的保留/引用等级')
    events=dialogue_events(text,planned)
    role_ids={}
    for _,role in events:
        role_ids.setdefault(role,len(role_ids)+1)
    subject_roles={}
    for line in definitions.splitlines():
        label=re.match(r'\s*(<Subject\s+\d+>)',line)
        roles=[role for role in role_ids if role in line]
        if label and len(roles)==1: subject_roles[label.group(1)]=roles[0]
    for line in definitions.splitlines():
        if re.match(r'\s*<Audio\s+\d+>',line):
            role_set={subject_roles[label] for label in re.findall(r'<Subject\s+\d+>',line) if label in subject_roles}
            ids=re.findall(r'\(S(\d+)\)',line)
            if len(role_set)==1 and ids and any(int(i)!=role_ids[next(iter(role_set))] for i in ids):
                pass  # Editorial warning only.

def requests_cut_example(idea):
    """Choose a cut example only with positive cut intent; never infer it from asset count."""
    text=str(idea)
    if re.search(r'一镜到底|单镜头|(?:不要|禁止|避免|不允许|不需要|无需|无|不)\s*(?:(?:任何|额外|突然|随意|主动|无故|新增)\s*)*(?:切镜|切到|切至|切换镜头|正反打)|\b(?:no|without|do not|don.t|never|avoid)\s+(?:(?:any|additional|extra|camera|sudden|unnecessary)\s+)*(?:cuts?|cutting)\b|\b(?:single[ -]shot|one[ -]shot|uncut)\b',text,re.I):
        return False
    return bool(re.search(r'切到|切至|正反打|跨镜头|匹配切镜|\bcut to\b|shot[ -]reverse[ -]shot',text,re.I))


def selected_example(assets_dir, mode, idea, has_audio=False):
    if mode=='h3_keyframe': name='keyframe'
    elif mode in ('h3_fl2va','h3_i2va','h3_l2va'): name='endpoints'
    elif requests_cut_example(idea): name='continuity'
    elif requests_group_speech(idea): name='group-dialogue'
    elif re.search(r'哼|呻吟|惊呼|喘息|笑声|nonverbal|gasp|groan',idea,re.I): name='vocal-performance'
    elif 'motion_context continuation' in idea: name='continuation'
    elif re.search(r'三人|三位|three (?:adult|people|person)',idea,re.I): name='multi-person'
    elif has_audio and mode=='h3_ref2va': name='voice-reference'
    elif re.search(r'广告|产品|商品|标语|字幕|包装|product|advert',idea,re.I): name='product'
    elif re.search(r'打斗|武打|搏斗|追逐|格斗|交接|递给|接过|combat|fight|handoff|chase',idea,re.I): name='action'
    else: name='dialogue'
    raw=(Path(assets_dir)/'examples'/f'{name}.md').read_text(encoding='utf-8')
    variants=raw.split('\n<!-- REF -->\n',1)
    selected=variants[1] if mode=='h3_ref2va' and len(variants)==2 else variants[0].removeprefix('<!-- BASE -->\n')
    if name=='endpoints' and mode in ('h3_i2va','h3_l2va'):
        preamble = ('For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.' if mode=='h3_i2va' else 'How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with the 6.00-second mark of the target video.')
        selected=re.sub(r'(?m)^How the reference pictures align[^\n]+',preamble,selected)
        selected=selected.replace('官方FL2VA','官方I2VA' if mode=='h3_i2va' else '官方L2VA')
        selected=selected.replace('首图杯子在桌左、末图杯子在桌右；I2VA/L2VA须改用本次所选单端指令。','只有首图，杯子从桌左移动，不虚构末图。' if mode=='h3_i2va' else '只有尾图，杯子终止在桌右，不虚构首图。')
        if mode=='h3_i2va':
            selected=selected.replace('到达末图位置后','滑动一小段后').replace('收敛到末图构图','在画面右侧停稳')
        else:
            selected=selected.replace('从首图左侧蓝色杯子的状态开始','蓝色杯子从桌面左侧开始，逐渐接近末图的右侧落点')
    return name, selected

def planning_rules():
    return [
        '继承用户/参考确立的媒介、风格、文字与声音，不默认改成写实电影；无对白或音乐要求时不擅自添加。',
        '用户给定人物名跨分段保持原文；无姓名使用稳定角色描述。区分角色名、视觉Subject与素材来源，不能因发言顺序、站位或换装而更换身份。',
        '对白按角色与顺序安排；保留用户给定原文，自创对白按剧情合理填写。非语言的哼声、呻吟、惊呼、笑声不强制填入dialogue_lines，写入可见动作和声音表现。',
        '分段按因果推进；只保留当前段有效素材。未听取音频/观看视频时不编造其中内容、节拍或音色分析。',
        '关键帧模式由本地Add Guide注入帧位；多模态参考与官方首尾帧为不同合同，不能混用标签。',
        '用片段实际时长安排对白、动作、反应与收尾；超过时长应精简动作，不删除用户逐字台词。',
        '段内连续事件默认单镜头；动作节拍、描述段落、参考图数量都不等于切镜。保留用户/参考/已批准计划确立的真实切镜或省略，不改成变形；段间transition服从调用方固定连续延长规则，后续段承接前段结束状态。',
        '在既有brief、opening_state、ending_state、continuity_from_previous内核对首尾和跨镜头的位置、朝向、姿态、接触、道具归属、动作与声音相位；不瞬移坐下或换手，未交代的必要变化须在规划中指出，不新增schema字段。',
        '保留等级针对定义的参考属性：自然动作、姿态和景别变化不自动降低身份/服装的fully_preserved；明确锁定的姿态、方向、关键帧或端点仍须遵守。',
    ]

def requires_dialogue(idea):
    text=re.sub(r'(?:无|没有|不含|无需|不要|禁止|不安排|不需要|不加|不写)\s*(?:任何)?\s*(?:对白|台词|旁白|独白|对话|说话)', '', str(idea))
    text=re.sub(r'\b(?:no|without)\s+(?:dialogue|speech|voice[ -]?over)\b','',text,flags=re.I)
    return bool(re.search(r'台词|对白|旁白|独白|对话|开口|说一句|说话|dialogue|voice[ -]?over|\bspeak\b|\bsays?\b',text,re.I))


def previous_shot_context(segment):
    """Carry authored camera/action intent; never describe it as measured video state."""
    if not segment:
        return {}
    prompt = str(segment.get("timeline_local_prompt") or segment.get("source_prompt") or segment.get("prompt") or "")
    fields = dict(sections(prompt))
    visual = fields.get("detailed_description") or fields.get("integrated_multimodal_description") or prompt
    return {
        "basis": "previous_prompt_intent_not_observed_video",
        "visual_description": visual,
        "ending_state": str(segment.get("ending_state") or ""),
        "rule": "Read the final shot's camera side, scale, direction, target and motion phase. Continue them without restarting; unspecified values remain unknown. Do not replay prior actions or claim frame measurements.",
    }


def subject_aliases(definitions):
    """Read explicit local aliases only; never infer a person's identity from appearance."""
    pairs = []
    for line in str(definitions).splitlines():
        label = re.match(r"\s*(<Subject\s+\d+>)", line)
        alias = re.search(r"(?:角色名|role name)\s*[：:]\s*([^）()，,；;。\n]+)", line, re.I)
        if label and alias:
            pairs.append((label.group(1), alias.group(1).strip()))
    return pairs


def identity_warnings(text, previous_definitions=""):
    """Report explicit mapping conflicts without guessing names or blocking generation."""
    fields = dict(sections(text))
    pairs = subject_aliases(fields.get("subject_definitions", ""))
    prior_pairs = subject_aliases(previous_definitions)
    prior = {alias: subject for subject, alias in prior_pairs}
    prior_subjects = dict(prior_pairs)
    warnings = []
    seen = {}
    for subject, alias in pairs:
        if alias in seen and seen[alias] != subject:
            warnings.append(f"角色名映射冲突：{alias} 同时绑定 {seen[alias]} 和 {subject}，请复核。")
        seen[alias] = subject
        if subject in prior_subjects and prior_subjects[subject] != alias:
            warnings.append(f"Subject角色名变化：{subject} 从 {prior_subjects[subject]} 变为 {alias}，请复核是否换人或改名。")
        if alias in prior and prior[alias] != subject:
            warnings.append(f"续写人物编号变化：{alias} 从 {prior[alias]} 变为 {subject}，请复核。")
    body = fields.get("detailed_description", "")
    for match in DIALOGUE.finditer(body):
        clause = re.split(r'[。！？\n]|</d>', body[:match.start()])[-1]
        for subject, alias in pairs:
            if alias in clause and subject not in clause and not re.search(r'<Subject\s+\d+>', clause):
                warnings.append(f"发言处缺少人物标签：{alias} 应明确绑定 {subject}，请复核。")
    return list(dict.fromkeys(warnings))


def subject_history(segments):
    """Retain known Subject definitions across temporary absences, latest wording wins."""
    definitions = {}
    for segment in segments:
        prompt = str(segment.get("timeline_local_prompt") or segment.get("source_prompt") or segment.get("prompt") or "")
        for line in dict(sections(prompt)).get("subject_definitions", "").splitlines():
            label = re.match(r"\s*(<Subject\s+\d+>)", line)
            if label:
                definitions[label.group(1)] = line.strip()
    return "\n".join(definitions.values())


def requests_group_speech(idea):
    text = re.sub(r'(?:不要|禁止|避免|没有|无|不)\s*(?:所有人|两人|大家)?\s*(?:合说|齐声|同时说|同时开口|同时喊)', '', str(idea))
    text = re.sub(r'\b(?:do not|never|without|no)\s+(?:speak(?:ing)? together|unison|group speech)', '', text, flags=re.I)
    return bool(re.search(r'合说|齐声|同时(?:说|开口|喊)|\bspeak together\b|\bunison\b|\bgroup speech\b', text, re.I))


def internal_role_bindings(segments):
    """Collect explicit legacy names/metadata without adding them to machine prose."""
    result = {}
    for segment in segments:
        for role, subject in (segment.get("role_bindings") or {}).items():
            if re.fullmatch(r'<Subject\s+\d+>', str(subject)):
                result[str(role)] = str(subject)
        raw = str(segment.get("source_prompt") or segment.get("timeline_local_prompt") or segment.get("prompt") or "")
        for subject, role in subject_aliases(dict(sections(raw)).get("subject_definitions", "")):
            result[role] = subject
    return result


def resolved_role_bindings(text, profiles, planned, previous=None):
    """Use explicit bindings or a unique role/source match; ambiguity stays unresolved."""
    result = dict(previous or {})
    definitions = dict(sections(text)).get("subject_definitions", "")
    pairs = subject_aliases(definitions)
    candidates = {}
    for subject, role in pairs:
        candidates.setdefault(role, set()).add(subject)
    subjects_by_media = {}
    for line in definitions.splitlines():
        subject = re.match(r'\s*(<Subject\s+\d+>)', line)
        if subject:
            for media in MEDIA.finditer(line):
                label = f'<{media.group(1).title()} {int(media.group(2))}>'
                subjects_by_media.setdefault(label, set()).add(subject.group(1))
    for planned_line in planned:
        role = re.split(r'[：:]', str(planned_line), maxsplit=1)[0].strip()
        if not role or role in result or role in candidates:
            continue
        media = [str(p.get("picture_id") or "") for p in profiles if role in str(p)]
        matches = set().union(*(subjects_by_media.get(label, set()) for label in media)) if media else set()
        if len(matches) == 1:
            candidates[role] = matches
    for role, subjects in candidates.items():
        if len(subjects) == 1:
            result[role] = next(iter(subjects))
        else:
            result.pop(role, None)
    return result


def subject_only_prompt(text, role_bindings=None):
    """Normalize only known aliases; speech and visible quoted text remain verbatim."""
    aliases = {}
    for role, subject in (role_bindings or {}).items():
        if re.fullmatch(r'<Subject\s+\d+>', str(subject)):
            aliases.setdefault(str(role), set()).add(str(subject))
    definitions = dict(sections(text)).get("subject_definitions", "")
    for subject, role in subject_aliases(definitions):
        aliases.setdefault(role, set()).add(subject)
    known = {role: next(iter(ids)) for role, ids in aliases.items() if len(ids) == 1 and role}
    protected = re.compile(r'(<d>.*?</d>|"(?:\\.|[^"\\])*"|“[^”]*”)', re.S)
    pieces = protected.split(str(text))
    for index in range(0, len(pieces), 2):
        prose = re.sub(r'[（(]\s*(?:角色名|role name)\s*[：:][^）)\n]*[）)]', '', pieces[index], flags=re.I)
        for role in sorted(known, key=len, reverse=True):
            label = known[role]
            prose = re.sub(re.escape(label) + r'[ \t]*[（(]\s*' + re.escape(role) + r'\s*[）)]', lambda _: label, prose)
            prose = re.sub(re.escape(label) + r'[ \t]*' + re.escape(role), lambda _: label, prose)
        if known:
            # Replace once, longest first; never cascade one alias replacement into another.
            pattern = '|'.join(
                (r'(?<![A-Za-z0-9_])' + re.escape(role) + r'(?![A-Za-z0-9_])')
                if re.search(r'[A-Za-z0-9]', role) else re.escape(role)
                for role in sorted(known, key=len, reverse=True)
            )
            prose = re.sub(pattern, lambda m: known[m.group(0)], prose)
        pieces[index] = prose
    return ''.join(pieces)


def inheritance_rules():
    return [
        "整体描述与全局声音是默认约束；逐段说明只覆盖其中明确指定的属性，空白或未提及的属性继承全局，不能将其他段专属内容复制到本段。",
        "自动声音仅补与已有场景和动作因果明确的必要环境底噪、脚步、衣料与接触声；整体或本段明确要求静音时不补。未知空间不臆造混响；不得自动新增对白、旁白、动物叫声、警报、音乐或新声源。用户已要求创作对白时可按原有规划规则创作。",
        "逐段明确例外只作用于本段，后续未指定段恢复继承全局；把覆盖关系和无法同时满足的声音、身份、场景、动作或时序冲突写入planning_warnings，指出段号、原要求、本段要求及采用方式，不静默丢弃要求。普通剧情推进不是冲突。",
        "全局声音字段与整体描述若互相矛盾也写入planning_warnings；不能靠省略用户原话隐藏冲突。仅将全段共同成立的指令编入global_prompt，存在逐段例外的限制在各段brief落实，避免编译时重新引入相互矛盾的全局句子。",
    ]


def description_language_rule(language):
    target = "English" if language == "English" else "Chinese"
    return (f"Description language is {target}, selected by the UI. This applies to global visual prose, "
            "subject definitions, action, camera and sound descriptions. Dialogue language is independent: "
            "preserve user-specified dialogue/lyrics in their original language inside <d>[Language]words</d>. "
            "A request for Chinese/Mandarin speech never changes English visual or sound prose. "
            "Preserve literal visible text and spoken names. English descriptions with Chinese dialogue are valid.")


def validate_description_language(text, language):
    if language != 'English':
        return
    prose = DIALOGUE.sub('', str(text))
    # Literal signage/branding may retain the user's original script.
    prose = re.sub(r'“[^”]*”|「[^」]*」|"[^"\n]*"', '', prose)
    if len(re.findall(r'[\u3400-\u9fff]', prose)) >= 12:
        raise ContractError('已选择English，动作、镜头、场景和声音正文必须为英文；仅对白/歌词及画面文字保留原语言，中文对白使用<d>[Chinese]原文</d>。')
