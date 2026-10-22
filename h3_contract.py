"""H3 prompt compilation checks; no inference or media processing."""
import re
from pathlib import Path

VERSION = '2026-10-22.1'
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
    return re.sub(r'\s+', ' ', re.sub(r'<(?:scenetrans|cutoff)>','',text)).strip()

def dialogue_events(text, planned):
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

def bind_dialogue(text, planned):
    events=dialogue_events(text,planned)
    if not events:
        return text
    role_ids={}
    for _,role in events:
        role_ids.setdefault(role,len(role_ids)+1)
    output=[]; cursor=0
    for match,role in events:
        between=text[cursor:match.start()]
        # A pause or previous spoken block does not change who is speaking.
        boundaries=list(re.finditer(r'[。！？\n]|<scenetrans>|<cutoff>',between))
        boundary=boundaries[-1].end() if boundaries else 0
        head,clause=between[:boundary],between[boundary:]
        for other in role_ids:
            if other!=role and re.match(rf'\s*{re.escape(other)}\s*(?:\(S\d+\)\s*)?(?:说道|回答|说|says\b|replies\b)',clause):
                raise ContractError('台词原文匹配，但明确标注的说话角色与计划不符')
        marker=f'(S{role_ids[role]})'
        ids=list(re.finditer(r'\(S\d+\)',clause))
        if ids:
            first=True
            def replace(_):
                nonlocal first
                if first:
                    first=False; return marker
                return ''
            clause=re.sub(r'\(S\d+\)',replace,clause)
        else:
            clause+=marker+' '
        output.extend((head,clause,match.group(0)))
        cursor=match.end()
    output.append(text[cursor:])
    return ''.join(output)

def validate_segment(text, planned, active_references, mode):
    bound = bind_dialogue(text,planned)
    parts = dict(sections(bound))
    body = parts.get('detailed_description', parts.get('integrated_multimodal_description',bound))
    cursor=0
    for match in DIALOGUE.finditer(body):
        prefix=body[cursor:match.start()]
        clause=re.split(r'[。！？\n]|<scenetrans>|<cutoff>',prefix)[-1]
        if len(re.findall(r'\(S\d+\)',clause))!=1:
            raise ContractError('每个实际发声子句必须有且仅有一个(SN)编号')
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
        raise ContractError('H3使用了未定义的Subject标签')
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
                raise ContractError('音频参考中的声纹编号与角色实际开口顺序不一致')

def requests_cut_example(idea):
    """Choose a cut example only with positive cut intent; never infer it from asset count."""
    text=str(idea)
    if re.search(r'一镜到底|单镜头|(?:不要|禁止|避免|不允许|不需要|无需|无|不)\s*(?:(?:任何|额外|突然|随意|主动|无故|新增)\s*)*(?:切镜|切到|切至|切换镜头|正反打)|\b(?:no|without|do not|don.t|never|avoid)\s+(?:(?:any|additional|extra|camera|sudden|unnecessary)\s+)*(?:cuts?|cutting)\b|\b(?:single[ -]shot|one[ -]shot|uncut)\b',text,re.I):
        return False
    return bool(re.search(r'切到|切至|正反打|跨镜头|匹配切镜|\bcut to\b|shot[ -]reverse[ -]shot',text,re.I))


def selected_example(assets_dir, mode, idea, has_audio=False):
    if mode=='h3_keyframe': name='keyframe'
    elif mode in ('h3_fl2va','h3_i2va','h3_l2va'): name='endpoints'
    elif has_audio and mode=='h3_ref2va': name='voice-reference'
    elif re.search(r'广告|产品|商品|标语|字幕|包装|product|advert',idea,re.I): name='product'
    elif requests_cut_example(idea): name='continuity'
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
        '逐字台词按本段实际发声顺序列为角色：原文。同一角色多句可分行；听者不重复台词。',
        '分段按因果推进；只保留当前段有效素材。未听取音频/观看视频时不编造其中内容、节拍或音色分析。',
        '关键帧模式由本地Add Guide注入帧位；多模态参考与官方首尾帧为不同合同，不能混用标签。',
        '用片段实际时长安排对白、动作、反应与收尾；超过时长应精简动作，不删除用户逐字台词。',
        '段内连续事件默认单镜头；动作节拍、描述段落、参考图数量都不等于切镜。保留用户/参考/已批准计划确立的真实切镜或省略，不改成变形；段间transition仍沿用原边界规则。',
        '在既有brief、opening_state、ending_state、continuity_from_previous内核对首尾和跨镜头的位置、朝向、姿态、接触、道具归属、动作与声音相位；不瞬移坐下或换手，未交代的必要变化须在规划中指出，不新增schema字段。',
        '保留等级针对定义的参考属性：自然动作、姿态和景别变化不自动降低身份/服装的fully_preserved；明确锁定的姿态、方向、关键帧或端点仍须遵守。',
    ]

def requires_dialogue(idea):
    text=re.sub(r'(?:无|没有|不含|无需|不要|禁止)\s*(?:任何)?\s*(?:对白|台词|旁白|独白|对话|说话)', '', str(idea))
    text=re.sub(r'\b(?:no|without)\s+(?:dialogue|speech|voice[ -]?over)\b','',text,flags=re.I)
    return bool(re.search(r'台词|对白|旁白|独白|对话|开口|说一句|说话|dialogue|voice[ -]?over|\bspeak\b|\bsays?\b',text,re.I))
